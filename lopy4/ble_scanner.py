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

    def deinit(self):
        """Libera el stack BLE."""
        try:
            self._bt.stop_scan()
        except Exception:
            pass
