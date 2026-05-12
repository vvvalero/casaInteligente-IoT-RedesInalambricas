# ble_scanner.py — Escáner BLE usando el chip integrado del LoPy4
# ============================================================
# El LoPy4 tiene BLE integrado (basado en ESP32).
# Este módulo usa el modo Observer para escanear dispositivos
# BLE cercanos y contar cuántos hay, lo que sirve como
# proxy de presencia/aforo sin necesidad de hardware adicional.
#
# No requiere ningún módulo externo: usa network.Bluetooth
# incluido en el firmware de Pycom.
# ============================================================

from network import Bluetooth
import time


class BLEScanner:

    # RSSI mínimo para considerar un dispositivo "presente"
    # -80 dBm es un umbral razonable (≈10 metros en interior)
    RSSI_UMBRAL = -80

    # Tiempo de escaneo activo en milisegundos
    SCAN_DURACION_MS = 3000

    def __init__(self):
        """Inicializa el stack BLE del LoPy4."""
        self._bt = Bluetooth()
        print('[BLE] Scanner inicializado')

    def escanear(self):
        """
        Realiza un escaneo BLE durante SCAN_DURACION_MS ms.

        Retorna un dict con:
            'total':      número total de dispositivos detectados
            'cercanos':   dispositivos con RSSI > RSSI_UMBRAL
            'rssi_medio': RSSI medio de todos los dispositivos
            'dispositivos': lista de dicts {mac, rssi, nombre}
        """
        dispositivos = {}

        def _callback(bt_o):
            """Callback llamado por cada advertisement recibido."""
            adv = bt_o.get_adv()
            if adv:
                mac  = ':'.join('{:02X}'.format(b) for b in adv.mac)
                rssi = adv.rssi
                # Intentar obtener nombre del dispositivo
                try:
                    nombre = adv.data_string.decode('utf-8', errors='ignore').strip()
                    nombre = nombre if nombre else 'desconocido'
                except Exception:
                    nombre = 'desconocido'

                # Guardar solo la entrada más reciente por MAC
                dispositivos[mac] = {'mac': mac, 'rssi': rssi, 'nombre': nombre}

        # Iniciar escaneo
        self._bt.start_scan(-1)   # -1 = escaneo continuo hasta stop
        self._bt.callback(trigger=Bluetooth.NEW_ADV_EVENT, handler=_callback)

        time.sleep_ms(self.SCAN_DURACION_MS)

        self._bt.stop_scan()
        self._bt.callback(trigger=Bluetooth.NEW_ADV_EVENT, handler=None)

        # Procesar resultados
        lista = list(dispositivos.values())
        total = len(lista)

        cercanos = [d for d in lista if d['rssi'] >= self.RSSI_UMBRAL]
        n_cercanos = len(cercanos)

        rssi_medio = 0
        if total > 0:
            rssi_medio = int(sum(d['rssi'] for d in lista) / total)

        resultado = {
            'total':        total,
            'cercanos':     n_cercanos,
            'rssi_medio':   rssi_medio,
            'dispositivos': lista
        }

        print('[BLE] Detectados: {} total, {} cercanos (RSSI > {} dBm)'.format(
            total, n_cercanos, self.RSSI_UMBRAL))

        return resultado

    def escanear_nfc_esp32(self, mac_objetivo, duracion_ms=3000):
        """
        Escanea buscando el ESP32-NFC por su MAC y extrae la cola de UIDs
        de su Manufacturer Specific Data (company ID 0x1234, cabecera "NFC").

        Retorna una lista de strings hex en mayúsculas (ej. ["A1B2C3D4", "DEADBEEF"])
        o [] si la cola está vacía o no se localiza el ESP32.
        Siempre toma el último paquete recibido para tener la cola más actualizada.
        """
        mac_objetivo = mac_objetivo.upper()
        ultima_cola = [[]]

        def _callback(bt_o):
            adv = bt_o.get_adv()
            if adv:
                mac = ':'.join('{:02X}'.format(b) for b in adv.mac)
                if mac == mac_objetivo:
                    ultima_cola[0] = self._parsear_cola_nfc(bytes(adv.data))

        self._bt.start_scan(-1)
        self._bt.callback(trigger=Bluetooth.NEW_ADV_EVENT, handler=_callback)
        time.sleep_ms(duracion_ms)
        self._bt.stop_scan()
        self._bt.callback(trigger=Bluetooth.NEW_ADV_EVENT, handler=None)

        uids = ultima_cola[0]
        if uids:
            print('[BLE-NFC] Cola: {} UID(s): {}'.format(len(uids), uids))
        else:
            print('[BLE-NFC] Cola vacía en ESP32 ({})'.format(mac_objetivo))

        return uids

    def _parsear_cola_nfc(self, data):
        """
        Recorre las estructuras AD del payload BLE buscando Manufacturer
        Specific Data (tipo 0xFF) con company ID 0x1234 y cabecera "NFC".

        Retorna una lista de strings hex con todos los UIDs de la cola.
        Formato del payload: [company(2)][NFC(3)][count][len1][uid1...][len2][uid2...]...
        """
        i = 0
        while i < len(data) - 1:
            length = data[i]
            if length == 0:
                break
            if i + length >= len(data):
                break
            ad_type = data[i + 1]
            # mínimo: company(2)+NFC(3)+count(1)+type(1) = 7
            if ad_type == 0xFF and length >= 7:
                payload = data[i + 2 : i + length + 1]
                if (len(payload) >= 6
                        and payload[0] == 0x34 and payload[1] == 0x12
                        and payload[2] == 0x4E and payload[3] == 0x46
                        and payload[4] == 0x43):
                    count = payload[5]
                    uids = []
                    pos = 6
                    for _ in range(count):
                        if pos >= len(payload):
                            break
                        uid_len = payload[pos]
                        pos += 1
                        if pos + uid_len > len(payload):
                            break
                        uid_hex = ''.join('{:02X}'.format(b)
                                          for b in payload[pos : pos + uid_len])
                        uids.append(uid_hex)
                        pos += uid_len
                    return uids
            i += length + 1
        return []

    def enviar_comando_led(self, mac_objetivo, led_id, red_on, green_on, timeout_ms=5000):
        """
        Se conecta al ESP32-NFC como cliente BLE y envía un comando de LED.
        
        Parámetros:
            mac_objetivo: MAC del ESP32 (ej. "AA:BB:CC:DD:EE:FF")
            led_id: ID del LED (1-6), se suma 1 internamente para el protocolo
            red_on: 0 o 1 (encender LED rojo/naranja)
            green_on: 0 o 1 (encender LED verde/azul)
            timeout_ms: tiempo máximo para conectar y escribir
        
        Retorna True si tuvo éxito, False si falló.
        
        Protocolo del ESP32:
            [led_id][red_on][green_on]
            Indicador 6 es para el LED de acceso NFC
        """
        try:
            mac_objetivo = mac_objetivo.upper()
            # Convertir MAC string "AA:BB:CC:DD:EE:FF" a bytes
            mac_bytes = bytes(int(x, 16) for x in mac_objetivo.split(':'))
            
            # Crear cliente BLE
            ble_client = self._bt.connect(mac_bytes)
            if not ble_client:
                print('[BLE-LED] No se pudo conectar a {}'.format(mac_objetivo))
                return False

            # UUIDs como bytes LE (lo que Pycom devuelve al leer GATT del ESP32-Arduino)
            # Servicio: a6e3ed8d-6a2f-4a8b-9b8c-1c9f8e7d6c5b → LE confirmado en log
            LED_SERVICE_UUID = "5b6c7d8e9f1c8c9b8b4a2f6a8dede3a6"
            # Característica: b1d2e3f4-5a6b-7c8d-9e0f-a1b2c3d4e5f6 → LE calculado
            LED_COMMAND_CHAR_UUID = "f6e5d4c3b2a10f9e8d7c6b5af4e3d2b1"

            def _uuid_norm(u):
                if isinstance(u, int):
                    return str(u)
                try:
                    # bytes o bytearray → hex directo
                    return ''.join('{:02x}'.format(b) for b in u)
                except TypeError:
                    return str(u).replace('-', '').lower()

            # Siempre desconectar, aunque falle la escritura
            try:
                services = ble_client.services()
                if services is None:
                    print('[BLE-LED] services() devolvió None')
                    return False

                target_char = None
                for srv in services:
                    if _uuid_norm(srv.uuid()) != LED_SERVICE_UUID:
                        continue
                    for ch in srv.characteristics():
                        if _uuid_norm(ch.uuid()) == LED_COMMAND_CHAR_UUID:
                            target_char = ch
                            break
                    break

                if not target_char:
                    print('[BLE-LED] Servicio/característica no encontrado')
                    return False

                # Construir y enviar comando: [led_id][red_on][green_on]
                comando = bytes([led_id, 1 if red_on else 0, 1 if green_on else 0])
                target_char.write(comando)

                print('[BLE-LED] LED {} R={} G={}'.format(
                    led_id, 1 if red_on else 0, 1 if green_on else 0))
                return True

            finally:
                ble_client.disconnect()
            
        except Exception as e:
            print('[BLE-LED] Error: {}'.format(e))
            return False

    def deinit(self):
        """Libera el stack BLE."""
        try:
            self._bt.stop_scan()
        except Exception:
            pass
