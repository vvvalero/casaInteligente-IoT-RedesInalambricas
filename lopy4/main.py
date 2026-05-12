# main.py — Casa Inteligente IoT · LoPy4 + Pysense
# ============================================================
# Soporta 3 tipos de nodo configurados via credentials.py:
#
#   NODE_TYPE = 'salon'
#     Sensores: temp, hum, lux, acelerómetro
#
#   NODE_TYPE = 'dormitorio'
#     Sensores: temp, hum, lux, NFC UID vía BLE (ESP32 + PN532)
#
#   NODE_TYPE = 'exterior'
#     Sensores: temp, hum, lux, BLE scanner
#
# Payload Cayenne LPP por nodo:
#   Salon:      CH1=temp CH2=hum CH3=lux CH4=accel CH5=room
#   Dormitorio: CH1=temp CH2=hum CH3=lux CH4=nfc_uid CH5=room
#   Exterior:   CH1=temp CH2=hum CH3=lux CH4=ble_count CH5=room
#
# Downlink (desde Fiware via TTN) — controla el LED RGB integrado:
#   Byte 0: comando
#     0x01 = set color RGB    (bytes 1=R 2=G 3=B)
#     0x02 = parpadear RGB    (bytes 1=R 2=G 3=B)
#     0x03 = acceso NFC concedido  (LED verde)
#     0x04 = acceso NFC denegado   (LED rojo)
#     0x05 = alerta aforo BLE      (LED amarillo)
#     0x06 = alerta temperatura    (byte 1: 0=frio→azul, 1=calor→naranja)
#     0x07 = alerta exterior       (LED blanco)
#     0x08 = sync whitelist NFC    (byte 1=count, luego 2 bytes por UID)
# ============================================================

import socket
import time
import binascii
import pycom
from network import LoRa
from CayenneLPP import CayenneLPP
from pysense import Pysense
from SI7006A20 import SI7006A20
from LTR329ALS01 import LTR329ALS01
from LIS2HH12 import LIS2HH12
from led import (sistema_arrancando, sistema_join_espera, sistema_conectado,
                 sistema_transmitiendo, sistema_error, sistema_downlink_recibido,
                 led_apagar, led_desde_bytes, led_rojo, led_verde, led_azul, led_amarillo,
                 led_naranja, led_blanco, led_magenta, parpadear)

# ============================================================
# CREDENCIALES Y CONFIGURACION
# ============================================================
try:
    from credentials import APP_EUI, APP_KEY, NODE_TYPE, TX_INTERVAL
except ImportError:
    print('ERROR: credentials.py no encontrado.')
    print('Copia credentials.example.py -> credentials.py y rellena tus datos.')
    import sys
    sys.exit()

# MAC del ESP32-NFC (solo necesaria en nodo dormitorio)
try:
    from credentials import ESP32_NFC_MAC
except ImportError:
    ESP32_NFC_MAC = None

# ============================================================
# WHITELIST NFC LOCAL — feedback inmediato sin esperar downlink
# ============================================================
_NFC_WL_FILE = '/flash/nfc_whitelist.txt'

def _cargar_whitelist():
    """Lee la whitelist del fichero en flash; si no existe usa el default de credentials."""
    try:
        with open(_NFC_WL_FILE, 'r') as f:
            return set(k.strip() for k in f.read().split(',') if k.strip())
    except OSError:
        pass
    try:
        from credentials import NFC_WHITELIST_DEFAULT
        return set(NFC_WHITELIST_DEFAULT)
    except ImportError:
        return set()

def _guardar_whitelist(wl):
    try:
        with open(_NFC_WL_FILE, 'w') as f:
            f.write(','.join(wl))
    except Exception as e:
        print('[WL] Error guardando: {}'.format(e))

NFC_WHITELIST_LOCAL = _cargar_whitelist()
print('[WL] Whitelist cargada: {} entradas: {}'.format(
    len(NFC_WHITELIST_LOCAL), NFC_WHITELIST_LOCAL))

# ============================================================
# ESTADO NFC — máquina de estados para el Indicador 6 del ESP32
# ============================================================
_NFC_IDLE    = 0
_NFC_PENDING = 1  # UID desconocido enviado al servidor, ámbar activo
_NFC_DONE    = 2  # Servidor respondió; verde o rojo mostrándose

_nfc_state     = _NFC_IDLE
_nfc_tracked   = None         # uid_key que se está verificando con el servidor
_last_nfc_uids = ['00000000'] # UIDs para incluir en el próximo uplink LoRa
_tx_ahora      = False        # True = lanzar uplink LoRa inmediatamente


def _uid_key(uid_str):
    n = int(uid_str[:8], 16) if len(uid_str) >= 8 else int(uid_str, 16)
    return '{:04X}'.format(n & 0xFFFF)


def _procesar_nfc(uids):
    """
    Evalúa UIDs detectados por el ESP32, actualiza el Indicador 6 del protoboard
    y activa _tx_ahora si hay un UID desconocido que necesita verificación en el servidor.
    """
    global _nfc_state, _nfc_tracked, _last_nfc_uids, _tx_ahora

    _last_nfc_uids = uids if uids else ['00000000']
    keys = [_uid_key(u) for u in uids]

    # UID rastreado ya no aparece en la cola del ESP32 (TTL expirado) y el servidor
    # ya respondió → podemos aceptar una nueva tarjeta limpiamente
    if _nfc_tracked and _nfc_tracked not in keys and _nfc_state == _NFC_DONE:
        _nfc_state   = _NFC_IDLE
        _nfc_tracked = None

    for uid_str in uids:
        key = _uid_key(uid_str)
        if key in NFC_WHITELIST_LOCAL:
            print('  NFC: {} → AUTORIZADO'.format(key))
            _nfc_state   = _NFC_IDLE
            _nfc_tracked = None
            if _ble and ESP32_NFC_MAC:
                _ble.enviar_comando_led(ESP32_NFC_MAC, 6, 0, 1)
        elif key != _nfc_tracked:
            # Nueva tarjeta desconocida (o distinta de la que ya estábamos rastreando)
            print('  NFC: {} → DESCONOCIDO — verificando servidor'.format(key))
            _nfc_state   = _NFC_PENDING
            _nfc_tracked = key
            _tx_ahora    = True
            if _ble and ESP32_NFC_MAC:
                _ble.enviar_comando_led(ESP32_NFC_MAC, 6, 1, 1)  # ámbar: verificando
        elif _nfc_state == _NFC_PENDING:
            # Mismo UID, todavía esperando respuesta del servidor.
            # TTN entrega el downlink solo cuando el LoPy4 hace TX, así que seguimos
            # pidiendo uplinks hasta que llegue el 0x03/0x04.
            _tx_ahora = True


if NODE_TYPE not in ('salon', 'dormitorio', 'exterior'):
    print('ERROR: NODE_TYPE invalido. Usa: salon | dormitorio | exterior')
    sistema_error()
    import sys
    sys.exit()

ROOM_ID = {'salon': 1, 'dormitorio': 2, 'exterior': 3}

# ============================================================
# INICIALIZACION DE HARDWARE COMUN (Pysense)
# ============================================================
sistema_arrancando()

py = Pysense()
si = SI7006A20(py)
lt = LTR329ALS01(py)

print('=== Casa Inteligente IoT ===')
print('Nodo: {}'.format(NODE_TYPE))
print('Intervalo TX: {} s'.format(TX_INTERVAL))
print('DevEUI: {}'.format(binascii.hexlify(LoRa().mac()).decode('utf-8').upper()))

# ============================================================
# INICIALIZACION ESPECIFICA POR NODO
# ============================================================
_mpl = None
_acc = None
_nfc = None
_ble = None

if NODE_TYPE == 'salon':
    try:
        _acc = LIS2HH12(py)
        print('[Salon] LIS2HH12 OK')
    except Exception as e:
        print('[Salon] LIS2HH12 no disponible: {}'.format(e))

elif NODE_TYPE == 'dormitorio':
    if ESP32_NFC_MAC:
        try:
            from ble_scanner import BLEScanner
            _ble = BLEScanner()
            print('[Dormitorio] BLE-NFC OK (ESP32: {})'.format(ESP32_NFC_MAC))
        except Exception as e:
            print('[Dormitorio] BLE-NFC no disponible: {}'.format(e))
    else:
        print('[Dormitorio] ESP32_NFC_MAC no configurado — NFC desactivado')

elif NODE_TYPE == 'exterior':
    try:
        from ble_scanner import BLEScanner
        _ble = BLEScanner()
        print('[Exterior] BLE scanner OK')
    except Exception as e:
        print('[Exterior] BLE scanner no disponible: {}'.format(e))

# ============================================================
# CONEXION LORAWAN (OTAA)
# ============================================================
lora = LoRa(mode=LoRa.LORAWAN, region=LoRa.EU868)
# NOTA: nvram_erase() solo se usa UNA VEZ al provisionar.
# NO descomentar en producción — borra la sesión guardada y fuerza rejoin cada arranque
# lora.nvram_erase()

def _joined():
    try:
        return lora.has_joined()
    except OSError:
        return False

print('Intentando join OTAA...')
join_backoff = 2
while not _joined():
    sistema_join_espera()
    try:
        lora.join(activation=LoRa.OTAA, auth=(APP_EUI, APP_KEY), timeout=15000)
    except OSError as e:
        print('  Error join: {}'.format(e))
    if not _joined():
        led_apagar()
        print('  Esperando join (reintentando en {}s)...'.format(join_backoff))
        time.sleep(join_backoff)
        join_backoff = min(join_backoff + 3, 30)

print('Join completado!')
sistema_conectado()

s = socket.socket(socket.AF_LORA, socket.SOCK_RAW)
s.setsockopt(socket.SOL_LORA, socket.SO_DR, 5)

# ============================================================
# LECTURAS POR NODO
# ============================================================

def _leer_comunes():
    return si.temperature(), si.humidity(), lt.light()[0]


def _leer_salon():
    temp, hum, lux = _leer_comunes()
    ax, ay, az = _acc.acceleration() if _acc else (0.0, 0.0, 0.0)

    print('  T={:.1f}C H={:.1f}% Lux={} Acc=({:.2f},{:.2f},{:.2f})g'.format(
        temp, hum, lux, ax, ay, az))

    magnitud = (ax**2 + ay**2 + az**2) ** 0.5
    if magnitud > 1.5:
        print('  ALERTA vibracion: {:.2f}g'.format(magnitud))
        parpadear(led_magenta, veces=2)

    lpp = CayenneLPP()
    lpp.add_temperature(1, temp)
    lpp.add_relative_humidity(2, hum)
    lpp.add_luminosity(3, lux)
    lpp.add_accelerometer(4, ax, ay, az)
    lpp.add_digital_input(5, ROOM_ID['salon'])
    return bytes(lpp.get_buffer())


def _leer_dormitorio():
    """Construye el payload LoRa con los últimos UIDs detectados por _procesar_nfc."""
    temp, hum, lux = _leer_comunes()
    print('  T={:.1f}C H={:.1f}% Lux={} NFC=[{}]'.format(
        temp, hum, lux,
        ', '.join(_last_nfc_uids) if _last_nfc_uids != ['00000000'] else 'vacío'))
    payloads = []
    for uid_str in _last_nfc_uids:
        uid_int = int(uid_str[:8], 16) if len(uid_str) >= 8 else int(uid_str, 16)
        uid_analog = (uid_int & 0xFFFF) / 100.0
        lpp = CayenneLPP()
        lpp.add_temperature(1, temp)
        lpp.add_relative_humidity(2, hum)
        lpp.add_luminosity(3, lux)
        lpp.add_analog_input(4, uid_analog)
        lpp.add_digital_input(5, ROOM_ID['dormitorio'])
        payloads.append(bytes(lpp.get_buffer()))
    return payloads


def _leer_exterior():
    temp, hum, lux = _leer_comunes()

    n_cercanos = 0
    if _ble:
        resultado = _ble.escanear()
        n_cercanos = resultado['cercanos']

    print('  T={:.1f}C H={:.1f}% Lux={} BLE={}'.format(
        temp, hum, lux, n_cercanos))

    if lux < 50:
        print('  Luminosidad baja exterior ({} lux)'.format(lux))
        parpadear(led_blanco, veces=1)

    lpp = CayenneLPP()
    lpp.add_temperature(1, temp)
    lpp.add_relative_humidity(2, hum)
    lpp.add_luminosity(3, lux)
    lpp.add_digital_input(4, min(n_cercanos, 255))
    lpp.add_digital_input(5, ROOM_ID['exterior'])
    return bytes(lpp.get_buffer())


# ============================================================
# PROCESADO DE DOWNLINK
# ============================================================

def _procesar_downlink(data):
    global _nfc_state
    if not data or len(data) < 1:
        return
    cmd = data[0]
    print('  Downlink cmd=0x{:02X}'.format(cmd))

    if cmd == 0x01 and len(data) >= 4:
        led_desde_bytes(data[1], data[2], data[3])
    elif cmd == 0x02 and len(data) >= 4:
        def _c():
            led_desde_bytes(data[1], data[2], data[3])
        parpadear(_c, veces=3)
    elif cmd == 0x03:
        parpadear(led_verde, veces=2, intervalo=0.4)
        if NODE_TYPE == 'dormitorio' and _ble and ESP32_NFC_MAC:
            _ble.enviar_comando_led(ESP32_NFC_MAC, 6, 0, 1)  # verde: acceso concedido
            _nfc_state = _NFC_DONE
    elif cmd == 0x04:
        parpadear(led_rojo, veces=3, intervalo=0.2)
        if NODE_TYPE == 'dormitorio' and _ble and ESP32_NFC_MAC:
            _ble.enviar_comando_led(ESP32_NFC_MAC, 6, 1, 0)  # rojo: acceso denegado
            _nfc_state = _NFC_DONE
    elif cmd == 0x05:
        parpadear(led_amarillo, veces=4, intervalo=0.2)
        led_amarillo()
    elif cmd == 0x06 and len(data) >= 2:
        if data[1] == 0:
            parpadear(led_azul, veces=3)
            led_azul()
        else:
            parpadear(led_naranja, veces=3)
            led_naranja()
    elif cmd == 0x07:
        parpadear(led_blanco, veces=2)
    elif cmd == 0x08 and len(data) >= 2:
        count = data[1]
        nueva_wl = set()
        for i in range(count):
            offset = 2 + i * 2
            if offset + 1 >= len(data):
                break
            nueva_wl.add('{:02X}{:02X}'.format(data[offset], data[offset + 1]))
        NFC_WHITELIST_LOCAL.clear()
        NFC_WHITELIST_LOCAL.update(nueva_wl)
        _guardar_whitelist(NFC_WHITELIST_LOCAL)
        print('  Whitelist sincronizada: {}'.format(NFC_WHITELIST_LOCAL))
    else:
        print('  Downlink desconocido: 0x{:02X}'.format(cmd))

    sistema_downlink_recibido()


# ============================================================
# BUCLE PRINCIPAL
# ============================================================
# Para dormitorio: el scan NFC (~3 s) marca la cadencia natural del bucle y puede
# disparar un uplink inmediato (_tx_ahora=True) cuando aparece un UID desconocido.
# Para salón/exterior: simple polling con sleep de 1 s entre comprobaciones.
_last_lora_tx = time.time() - TX_INTERVAL  # fuerza TX en el primer ciclo

while True:
    # --- Reconexión LoRa si se perdió la sesión ---
    if not _joined():
        print('ERROR: Perdida conexion LoRa, rejoin necesario')
        while not _joined():
            sistema_join_espera()
            try:
                lora.join(activation=LoRa.OTAA, auth=(APP_EUI, APP_KEY), timeout=15000)
            except OSError:
                pass
            if not lora.has_joined():
                led_apagar()
                time.sleep(5)
        sistema_conectado()
        print('Reconectado a LoRa')

    # --- Scan NFC (solo dormitorio; la ventana de 3 s marca la cadencia del bucle) ---
    if NODE_TYPE == 'dormitorio':
        print('  [WL] {} entradas: {}'.format(
            len(NFC_WHITELIST_LOCAL), sorted(NFC_WHITELIST_LOCAL)))
        if _ble and ESP32_NFC_MAC:
            uids = _ble.escanear_nfc_esp32(ESP32_NFC_MAC)
            _procesar_nfc(uids)

    # --- Uplink LoRa: periódico o disparado por UID desconocido ---
    if _tx_ahora or (time.time() - _last_lora_tx >= TX_INTERVAL):
        _tx_ahora = False
        print('\n--- Uplink {} ---'.format(NODE_TYPE))

        try:
            if NODE_TYPE == 'salon':
                payloads = [_leer_salon()]
            elif NODE_TYPE == 'dormitorio':
                payloads = _leer_dormitorio()
            elif NODE_TYPE == 'exterior':
                payloads = [_leer_exterior()]
        except Exception as e:
            print('  Error sensores: {}'.format(e))
            sistema_error()
            _last_lora_tx = time.time()
            sistema_conectado()
            continue

        n = len(payloads)
        for idx, payload in enumerate(payloads):
            print('  Payload {}/{} ({} bytes): {}'.format(
                idx + 1, n, len(payload),
                binascii.hexlify(payload).decode('utf-8').upper()
            ))

            sistema_transmitiendo()
            s.setblocking(True)
            s.settimeout(3.5)

            send_ok = False
            for retry in range(2):
                try:
                    s.send(payload)
                    print('  Uplink enviado')
                    send_ok = True
                    break
                except Exception as e:
                    print('  Error enviando (intento {}/2): {}'.format(retry + 1, e))
                    if retry < 1:
                        time.sleep(1)

            if not send_ok:
                print('  Fallo envío después de retries')
                sistema_conectado()
                continue

            try:
                data = s.recv(64)
                if data:
                    print('  Downlink: {}'.format(
                        binascii.hexlify(data).decode('utf-8').upper()))
                    _procesar_downlink(data)
                else:
                    print('  Sin downlink (buffer vacío)')
                    sistema_conectado()
            except socket.timeout:
                print('  Sin downlink (timeout RX)')
                sistema_conectado()
            except Exception as e:
                print('  Error recibiendo: {}'.format(e))
                sistema_conectado()

            if idx < n - 1:
                time.sleep(2)

        _last_lora_tx = time.time()

    elif NODE_TYPE != 'dormitorio':
        # Salón/exterior sin NFC: pequeña pausa para no hacer busy-wait
        time.sleep(1)
