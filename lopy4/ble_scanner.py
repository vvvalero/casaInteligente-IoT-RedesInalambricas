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

    def deinit(self):
        """Libera el stack BLE."""
        try:
            self._bt.stop_scan()
        except Exception:
            pass
