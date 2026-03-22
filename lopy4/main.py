# main.py — Casa Inteligente IoT · LoPy4 + Pysense
# ============================================================
# Soporta 3 tipos de nodo configurados via credentials.py:
#
#   NODE_TYPE = 'salon'
#     Sensores: temp, hum, lux, presión, acelerómetro
#     LED externo controlado por downlink (color RGB)
#
#   NODE_TYPE = 'dormitorio'
#     Sensores: temp, hum, lux, NFC (PN532)
#     LED externo: verde=acceso OK, rojo=acceso denegado
#
#   NODE_TYPE = 'exterior'
#     Sensores: temp, hum, presión, BLE scanner
#     LED externo: alerta de aforo y luminosidad
#
# Payload Cayenne LPP por nodo:
#   Salon:      CH1=temp CH2=hum CH3=lux CH4=pres CH5=accel CH6=room
#   Dormitorio: CH1=temp CH2=hum CH3=lux CH4=nfc_uid CH5=room
#   Exterior:   CH1=temp CH2=hum CH3=pres CH4=ble_count CH5=room
#
# Downlink (desde Fiware via TTN):
#   Byte 0: comando
#     0x01 = set LED RGB  (bytes 1=R 2=G 3=B)
#     0x02 = parpadear LED RGB
#     0x03 = acceso NFC concedido  (LED verde)
#     0x04 = acceso NFC denegado   (LED rojo)
#     0x05 = alerta aforo BLE      (LED amarillo)
#     0x06 = alerta temperatura    (byte 1: 0=frio 1=calor)
#     0x07 = alerta exterior       (LED blanco)
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
from MPL3115A2 import MPL3115A2, PRESSURE
from LIS2HH12 import LIS2HH12
from led import (sistema_arrancando, sistema_join_espera, sistema_conectado,
                 sistema_transmitiendo, sistema_error, sistema_downlink_recibido,
                 led_desde_bytes, led_rojo, led_verde, led_azul, led_amarillo,
                 led_naranja, led_blanco, led_magenta, leds_apagar, parpadear)

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
        _mpl = MPL3115A2(py, mode=PRESSURE)
        print('[Salon] MPL3115A2 OK')
    except Exception as e:
        print('[Salon] MPL3115A2 no disponible: {}'.format(e))
    try:
        _acc = LIS2HH12(py)
        print('[Salon] LIS2HH12 OK')
    except Exception as e:
        print('[Salon] LIS2HH12 no disponible: {}'.format(e))

elif NODE_TYPE == 'dormitorio':
    try:
        from nfc import PN532
        _nfc = PN532()
        print('[Dormitorio] PN532 OK')
    except Exception as e:
        print('[Dormitorio] PN532 no disponible: {}'.format(e))

elif NODE_TYPE == 'exterior':
    try:
        _mpl = MPL3115A2(py, mode=PRESSURE)
        print('[Exterior] MPL3115A2 OK')
    except Exception as e:
        print('[Exterior] MPL3115A2 no disponible: {}'.format(e))
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
lora.join(activation=LoRa.OTAA, auth=(APP_EUI, APP_KEY), timeout=0)

print('Intentando join OTAA...')
while not lora.has_joined():
    sistema_join_espera()
    time.sleep(2.5)
    pycom.rgbled(0x000000)
    time.sleep(1.0)
    print('  Esperando join...')

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
    pres = _mpl.pressure() / 100.0 if _mpl else 1013.0
    ax, ay, az = _acc.acceleration() if _acc else (0.0, 0.0, 0.0)

    print('  T={:.1f}C H={:.1f}% Lux={} P={:.1f}hPa Acc=({:.2f},{:.2f},{:.2f})g'.format(
        temp, hum, lux, pres, ax, ay, az))

    # Alerta local vibración > 1.5g
    magnitud = (ax**2 + ay**2 + az**2) ** 0.5
    if magnitud > 1.5:
        print('  ALERTA vibracion: {:.2f}g'.format(magnitud))
        parpadear(led_magenta, veces=2)
        sistema_conectado()

    lpp = CayenneLPP()
    lpp.add_temperature(1, temp)
    lpp.add_relative_humidity(2, hum)
    lpp.add_luminosity(3, lux)
    lpp.add_barometric_pressure(4, pres)
    lpp.add_accelerometer(5, ax, ay, az)
    lpp.add_digital_input(6, ROOM_ID['salon'])
    return bytes(lpp.get_buffer()), None


def _leer_dormitorio():
    temp, hum, lux = _leer_comunes()

    uid_str = '00000000'
    uid_analog = 0.0
    if _nfc:
        uid = _nfc.leer_uid(timeout_ms=2000)
        if uid:
            uid_str = uid
            uid_int = int(uid[:8], 16) if len(uid) >= 8 else int(uid, 16)
            uid_analog = (uid_int & 0xFFFF) / 100.0
            print('  NFC UID: {}'.format(uid_str))
        else:
            print('  NFC: sin tarjeta')

    print('  T={:.1f}C H={:.1f}% Lux={} NFC={}'.format(temp, hum, lux, uid_str))

    lpp = CayenneLPP()
    lpp.add_temperature(1, temp)
    lpp.add_relative_humidity(2, hum)
    lpp.add_luminosity(3, lux)
    lpp.add_analog_input(4, uid_analog)
    lpp.add_digital_input(5, ROOM_ID['dormitorio'])
    return bytes(lpp.get_buffer()), uid_str


def _leer_exterior():
    temp, hum, lux = _leer_comunes()
    pres = _mpl.pressure() / 100.0 if _mpl else 1013.0

    n_cercanos = 0
    if _ble:
        resultado = _ble.escanear()
        n_cercanos = resultado['cercanos']

    print('  T={:.1f}C H={:.1f}% P={:.1f}hPa BLE={}'.format(
        temp, hum, pres, n_cercanos))

    # Alerta local luminosidad baja exterior
    if lux < 50:
        print('  Luminosidad baja exterior ({} lux)'.format(lux))
        parpadear(led_blanco, veces=1)
        sistema_conectado()

    lpp = CayenneLPP()
    lpp.add_temperature(1, temp)
    lpp.add_relative_humidity(2, hum)
    lpp.add_barometric_pressure(3, pres)
    lpp.add_digital_input(4, min(n_cercanos, 255))
    lpp.add_digital_input(5, ROOM_ID['exterior'])
    return bytes(lpp.get_buffer()), None


# ============================================================
# PROCESADO DE DOWNLINK
# ============================================================

def _procesar_downlink(data):
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
        sistema_conectado()
    elif cmd == 0x03:
        parpadear(led_verde, veces=2, intervalo=0.4)
        led_verde()
    elif cmd == 0x04:
        parpadear(led_rojo, veces=3, intervalo=0.2)
        leds_apagar()
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
        led_blanco()
    else:
        print('  Downlink desconocido: 0x{:02X}'.format(cmd))

    sistema_downlink_recibido()


# ============================================================
# BUCLE PRINCIPAL
# ============================================================
while True:
    print('\n--- Ciclo {} ---'.format(NODE_TYPE))

    try:
        if NODE_TYPE == 'salon':
            payload, extra = _leer_salon()
        elif NODE_TYPE == 'dormitorio':
            payload, extra = _leer_dormitorio()
        elif NODE_TYPE == 'exterior':
            payload, extra = _leer_exterior()
    except Exception as e:
        print('  Error sensores: {}'.format(e))
        sistema_error()
        time.sleep(TX_INTERVAL)
        sistema_conectado()
        continue

    print('  Payload ({} bytes): {}'.format(
        len(payload),
        binascii.hexlify(payload).decode('utf-8').upper()
    ))

    sistema_transmitiendo()
    s.setblocking(True)
    s.send(payload)
    print('  Uplink enviado')

    s.setblocking(False)
    data = s.recv(64)

    if data:
        print('  Downlink: {}'.format(
            binascii.hexlify(data).decode('utf-8').upper()))
        _procesar_downlink(data)
    else:
        print('  Sin downlink')
        sistema_conectado()

    print('  Siguiente envio en {} s'.format(TX_INTERVAL))
    time.sleep(TX_INTERVAL)
