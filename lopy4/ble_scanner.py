# ble_scanner.py — Escáner BLE con el chip integrado del LoPy4
# Usa network.Bluetooth (Pycom firmware) para contar dispositivos
# cercanos (proxy de aforo) y leer la cola NFC del ESP32.

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
        Reintenta una vez con 600 ms de pausa si la primera conexión falla
        (el stack BLE de Pycom necesita margen tras stop_scan).
        """
        mac_objetivo = mac_objetivo.upper()
        mac_bytes = bytes(int(x, 16) for x in mac_objetivo.split(':'))

        LED_SERVICE_UUID      = "5b6c7d8e9f1c8c9b8b4a2f6a8dede3a6"
        LED_COMMAND_CHAR_UUID = "f6e5d4c3b2a10f9e8d7c6b5af4e3d2b1"

        def _uuid_norm(u):
            if isinstance(u, int):
                return str(u)
            try:
                return ''.join('{:02x}'.format(b) for b in u)
            except TypeError:
                return str(u).replace('-', '').lower()

        _delays = [300, 800, 1500]
        for attempt in range(3):
            ble_client = None
            try:
                # stop_scan() antes de connect fuerza al stack BLE de Pycom a salir
                # de cualquier estado scan residual (no-op si no hay scan activo)
                try:
                    self._bt.stop_scan()
                except Exception:
                    pass
                time.sleep_ms(_delays[attempt])

                ble_client = self._bt.connect(mac_bytes)
                if not ble_client:
                    raise Exception('connect returned None')

                services = ble_client.services()
                if services is None:
                    raise Exception('services() devolvió None')

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
                    raise Exception('servicio/característica no encontrado')

                target_char.write(bytes([led_id, 1 if red_on else 0, 1 if green_on else 0]))
                print('[BLE-LED] LED {} R={} G={}'.format(
                    led_id, 1 if red_on else 0, 1 if green_on else 0))
                return True

            except Exception as e:
                print('[BLE-LED] Error (intento {}/3): {}'.format(attempt + 1, e))
            finally:
                if ble_client:
                    try:
                        ble_client.disconnect()
                    except Exception:
                        pass

        return False

    def enviar_batch_leds(self, mac_objetivo, states):
        """
        Conecta al ESP32 UNA SOLA VEZ y envía múltiples comandos de LED.
        states: lista de (led_id, red_on, green_on)
        Reintenta una vez con 600 ms de pausa si la conexión falla.
        """
        mac_objetivo = mac_objetivo.upper()
        mac_bytes = bytes(int(x, 16) for x in mac_objetivo.split(':'))

        LED_SERVICE_UUID      = "5b6c7d8e9f1c8c9b8b4a2f6a8dede3a6"
        LED_COMMAND_CHAR_UUID = "f6e5d4c3b2a10f9e8d7c6b5af4e3d2b1"

        def _uuid_norm(u):
            if isinstance(u, int):
                return str(u)
            try:
                return ''.join('{:02x}'.format(b) for b in u)
            except TypeError:
                return str(u).replace('-', '').lower()

        _delays = [300, 800, 1500]
        for attempt in range(3):
            ble_client = None
            try:
                try:
                    self._bt.stop_scan()
                except Exception:
                    pass
                time.sleep_ms(_delays[attempt])

                ble_client = self._bt.connect(mac_bytes)
                if not ble_client:
                    raise Exception('connect returned None')

                services = ble_client.services()
                if services is None:
                    raise Exception('services() devolvió None')

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
                    raise Exception('servicio/característica no encontrado')

                for led_id, red_on, green_on in states:
                    target_char.write(bytes([led_id, 1 if red_on else 0, 1 if green_on else 0]))

                print('[BLE-LED] Batch {} indicadores OK'.format(len(states)))
                return True

            except Exception as e:
                print('[BLE-LED] Batch error (intento {}/3): {}'.format(attempt + 1, e))
            finally:
                if ble_client:
                    try:
                        ble_client.disconnect()
                    except Exception:
                        pass

        return False

    def deinit(self):
        """Libera el stack BLE."""
        try:
            self._bt.stop_scan()
        except Exception:
            pass
