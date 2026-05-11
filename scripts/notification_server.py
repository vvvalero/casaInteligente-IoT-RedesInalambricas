#!/usr/bin/env python3
# notification_server.py — Servidor de automatización Casa Inteligente IoT
#
# Soporta dos modos de despliegue:
#   Local (WSL2): credenciales editadas directamente en este fichero
#   DMZ (Docker): credenciales leídas de variables de entorno (.env)
#
# Las variables de entorno tienen prioridad sobre los valores hardcodeados.

from flask import Flask, request, jsonify
from flask_cors import CORS
import requests, json, logging, base64, time, os, re, asyncio, threading
from datetime import datetime, timezone
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

try:
    from bleak import BleakClient
    BLEAK_AVAILABLE = True
except ImportError:
    BLEAK_AVAILABLE = False
    logging.warning("bleak no instalada. Control BLE de LEDs desactivado. Instala: pip install bleak")

app = Flask(__name__)
CORS(app)
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s [%(levelname)s] %(message)s')

# Connection pooling: reutiliza conexiones TCP para mejorar concurrencia
_session = requests.Session()
retry_strategy = Retry(total=2, status_forcelist=[429, 500, 502, 503, 504], allowed_methods=["GET", "POST", "PATCH"])
adapter = HTTPAdapter(max_retries=retry_strategy, pool_connections=20, pool_maxsize=20)
_session.mount("http://", adapter)
_session.mount("https://", adapter)

# ============================================================
# BLE LED CLIENT (Control de ESP32)
# ============================================================
class BLELEDClient:
    """Cliente BLE para controlar LEDs del ESP32"""
    def __init__(self, device_name="ESP32-NFC-Door"):
        self.device_name = device_name
        self.address = None
        self.client = None
        self.loop = None
        self.char_uuid = "b1d2e3f4-5a6b-7c8d-9e0f-a1b2c3d4e5f6"
        self.connected = False
        self._lock = threading.Lock()
        self._running = True
        self._reconnect_attempts = 0
        self._max_reconnect_attempts = 5

    async def _find_device(self):
        """Busca el ESP32 por nombre"""
        try:
            from bleak import BleakScanner
            devices = await BleakScanner.discover(timeout=5.0)
            for device in devices:
                if self.device_name in (device.name or ""):
                    self.address = device.address
                    logging.info(f"[BLE] ESP32 encontrado: {self.address}")
                    return True
            logging.warning(f"[BLE] {self.device_name} no encontrado")
            return False
        except Exception as e:
            logging.error(f"[BLE] Error buscando dispositivo: {e}")
            return False

    async def connect(self):
        """Conecta al ESP32"""
        if not BLEAK_AVAILABLE:
            return False
        try:
            if not self.address:
                if not await self._find_device():
                    return False
            self.client = BleakClient(self.address)
            await self.client.connect()
            self.connected = True
            logging.info(f"[BLE] Conectado a {self.device_name}")

            # Enviar comandos pendientes de la cola
            try:
                await asyncio.sleep(0.5)
                loop = asyncio.get_event_loop()
                loop.call_soon_threadsafe(_flush_led_queue)
            except:
                pass

            return True
        except Exception as e:
            logging.error(f"[BLE] Error conectando: {e}")
            self.connected = False
            return False

    async def disconnect(self):
        """Desconecta del ESP32"""
        try:
            if self.client and self.connected:
                await self.client.disconnect()
                self.connected = False
                logging.info("[BLE] Desconectado")
        except Exception as e:
            logging.error(f"[BLE] Error desconectando: {e}")

    async def send_led_command(self, led_id, red_on, green_on):
        """Envía comando de LED simple: [led_id][red_on][green_on]"""
        if not self.connected or not self.client:
            return False
        try:
            command = bytes([led_id, 1 if red_on else 0, 1 if green_on else 0])
            state = "AMARILLO" if (red_on and green_on) else ("ROJO" if red_on else "VERDE")
            await self.client.write_gatt_char(self.char_uuid, command)
            logging.info(f"[BLE] Indicador {led_id} → {state}")
            return True
        except Exception as e:
            logging.error(f"[BLE] Error escribiendo LED: {e}")
            self.connected = False
            return False

    def run_in_thread(self):
        """Ejecuta el loop async en un thread con reconexión automática"""
        try:
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)

            self.loop.run_until_complete(self._reconnect_loop())

        except Exception as e:
            logging.error(f"[BLE] Error fatal en thread: {e}")
        finally:
            if self.loop:
                self.loop.close()
            self._running = False

    async def _reconnect_loop(self):
        """Loop asíncrono de reconexión"""
        reconnect_delay = 1
        while self._running:
            try:
                if not self.connected:
                    logging.info(f"[BLE] Intentando conectar... (intento {self._reconnect_attempts + 1})")
                    if await self.connect():
                        self._reconnect_attempts = 0
                        reconnect_delay = 1
                    else:
                        self._reconnect_attempts += 1
                        if self._reconnect_attempts >= self._max_reconnect_attempts:
                            logging.error(f"[BLE] Máximo de intentos alcanzado ({self._max_reconnect_attempts})")
                            reconnect_delay = 30
                        else:
                            reconnect_delay = min(reconnect_delay * 2, 10)

                await asyncio.sleep(reconnect_delay)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logging.error(f"[BLE] Error en loop de reconexión: {e}")
                await asyncio.sleep(5)

    def stop(self):
        """Detiene el thread BLE de forma segura"""
        self._running = False
        if self.loop:
            try:
                self.loop.call_soon_threadsafe(lambda: None)
            except:
                pass

    def send_led(self, led_id, red_on, green_on):
        """Interfaz sync para enviar LED con reintento"""
        if not BLEAK_AVAILABLE:
            return False

        try:
            if not self.loop or not self.loop.is_running():
                return False

            for attempt in range(2):
                try:
                    future = asyncio.run_coroutine_threadsafe(
                        self.send_led_command(led_id, red_on, green_on), self.loop)
                    result = future.result(timeout=2)
                    if result:
                        return True
                except asyncio.TimeoutError:
                    logging.warning(f"[BLE] Timeout enviando indicador {led_id}")
                except Exception as e:
                    logging.debug(f"[BLE] Error intento {attempt + 1}: {e}")

                if attempt == 0 and not self.connected:
                    logging.warning(f"[BLE] Desconectado, reintentando...")
                    time.sleep(0.5)

        except Exception as e:
            logging.error(f"[BLE] Error enviando LED: {e}")

        return False


# Cliente BLE global
_ble_client = None

def _init_ble_client():
    """Inicializa el cliente BLE en un thread"""
    global _ble_client
    if not BLEAK_AVAILABLE:
        logging.warning("[BLE] bleak no disponible, LEDs desactivados")
        return
    try:
        _ble_client = BLELEDClient()
        ble_thread = threading.Thread(target=_ble_client.run_in_thread, daemon=True)
        ble_thread.start()
        logging.info("[BLE] Cliente BLE iniciando...")
    except Exception as e:
        logging.error(f"[BLE] Error inicializando: {e}")

_led_command_queue = []
_led_queue_lock = threading.Lock()
_LED_QUEUE_MAX_SIZE = 50  # Límite para evitar OOM

def _send_led(led_id, red_on, green_on):
    """Envía comando de LED al ESP32 vía BLE con cola de respaldo (máx 50 comandos)"""
    global _led_command_queue

    if not BLEAK_AVAILABLE or not _ble_client:
        return False

    # Validar que led_id esté en rango [1,7]
    if led_id < 1 or led_id > 7:
        logging.error(f"[BLE] Indicador {led_id} inválido (debe ser 1-7)")
        return False

    # Intentar enviar directamente
    if _ble_client.send_led(led_id, red_on, green_on):
        # Éxito, limpiar comandos de la cola para este LED (deduplicación)
        with _led_queue_lock:
            _led_command_queue = [(id, r, g) for id, r, g in _led_command_queue if id != led_id]
        return True

    # Si falla y no está conectado, agregar a cola (con límite de tamaño)
    if not _ble_client.connected:
        with _led_queue_lock:
            # Remover comando anterior del mismo LED (deduplicación)
            _led_command_queue = [(id, r, g) for id, r, g in _led_command_queue if id != led_id]

            # Agregar nuevo comando si hay espacio
            if len(_led_command_queue) < _LED_QUEUE_MAX_SIZE:
                _led_command_queue.append((led_id, red_on, green_on))
                logging.debug(f"[BLE] Comando indicador {led_id} agregado a cola (desconectado, {len(_led_command_queue)}/{_LED_QUEUE_MAX_SIZE})")
            else:
                logging.warning(f"[BLE] Cola de LEDs llena ({_LED_QUEUE_MAX_SIZE}), descartando indicador {led_id}")
        return False

    return False

def _flush_led_queue():
    """Envía todos los comandos pendientes de la cola"""
    global _led_command_queue

    if not _ble_client or not _ble_client.connected:
        return 0

    with _led_queue_lock:
        if not _led_command_queue:
            return 0

        queue_copy = _led_command_queue.copy()
        _led_command_queue.clear()

    sent = 0
    for led_id, red_on, green_on in queue_copy:
        if _ble_client.send_led(led_id, red_on, green_on):
            sent += 1
        else:
            with _led_queue_lock:
                _led_command_queue.append((led_id, red_on, green_on))

    if sent > 0:
        logging.info(f"[BLE] {sent} comandos enviados desde cola")

    return sent


# ============================================================
# GESTOR DE ESTADO GLOBAL DE LEDs
# ============================================================
class LEDStateManager:
    """Gestiona estado de alertas y LEDs por nodo y tipo"""

    def __init__(self):
        self.node_alerts = {
            "Sensor:s1": set(),
            "Sensor:s2": set(),
            "Sensor:s3": set()
        }
        self.type_alerts = {
            "temp": set(),
            "pressure": set(),
            "humidity": set()
        }
        self._lock = threading.Lock()

    def add_alert(self, sensor_id, alert_type):
        """Agrega alerta para un nodo/tipo"""
        with self._lock:
            if sensor_id in self.node_alerts:
                self.node_alerts[sensor_id].add(alert_type)
            if alert_type in self.type_alerts:
                self.type_alerts[alert_type].add(sensor_id)
            led_updates = self._calculate_led_colors()

        # Enviar LEDs sin tener el lock (evita bloqueo de I/O dentro del lock)
        for led_id, red_on, green_on in led_updates:
            _send_led(led_id, red_on, green_on)

    def remove_alert(self, sensor_id, alert_type):
        """Elimina alerta para un nodo/tipo"""
        with self._lock:
            if sensor_id in self.node_alerts:
                self.node_alerts[sensor_id].discard(alert_type)
            if alert_type in self.type_alerts:
                self.type_alerts[alert_type].discard(sensor_id)
            led_updates = self._calculate_led_colors()

        # Enviar LEDs sin tener el lock (evita bloqueo de I/O dentro del lock)
        for led_id, red_on, green_on in led_updates:
            _send_led(led_id, red_on, green_on)

    def _calculate_led_colors(self):
        """Calcula qué LEDs deben estar on/off según estado actual.
        DEBE ser llamado DENTRO del lock. Devuelve lista de (led_id, red_on, green_on) tuplas."""
        updates = []

        # Indicadores 1-3: Estado por nodo
        for i, sensor_id in enumerate(["Sensor:s1", "Sensor:s2", "Sensor:s3"], 1):
            if self.node_alerts[sensor_id]:
                updates.append((i, True, False))  # Rojo (alerta)
            else:
                updates.append((i, False, True))  # Verde (OK)

        # Indicadores 4-6: Alertas por tipo
        alert_leds = {
            "temp": 4,
            "pressure": 5,
            "humidity": 6
        }
        for alert_type, led_id in alert_leds.items():
            if self.type_alerts[alert_type]:
                count = len(self.type_alerts[alert_type])
                if count >= 2:
                    updates.append((led_id, True, True))  # Amarillo (crítico, ambos encendidos)
                else:
                    updates.append((led_id, True, False))  # Rojo (alerta)
            else:
                updates.append((led_id, False, True))  # Verde (OK)

        # Indicador 7: Sistema general
        all_alerts = set()
        for alerts in self.node_alerts.values():
            all_alerts.update(alerts)

        if "nfc_denied" in all_alerts or "vibration" in all_alerts:
            updates.append((7, True, False))  # Rojo (crítico)
        elif all_alerts:
            updates.append((7, True, True))  # Amarillo (warning, ambos encendidos)
        else:
            updates.append((7, False, True))  # Verde (OK)

        return updates


_led_manager = LEDStateManager()


# ============================================================
# CONFIG
# Variables de entorno tienen prioridad (despliegue Docker/DMZ)
# Si no están definidas, usa los valores hardcodeados (uso local)
# ============================================================

# URL de Orion — en Docker usa el nombre del servicio, en local usa localhost
ORION = os.environ.get("ORION_URL", "http://localhost:1026")

FS_HEADERS = {
    "Content-Type":       "application/json",
    "fiware-service":     "smarthome",
    "fiware-servicepath": "/"
}

# TTN — editar aquí para uso local, o configurar en .env para DMZ
TTN_APP_ID   = os.environ.get("TTN_APP_ID",  "casa-iot")
TTN_API_KEY  = os.environ.get("TTN_API_KEY", "NNSXS.XXXXXXXXXX")
TTN_API_BASE = "https://eu1.cloud.thethings.network/api/v3"

SENSOR_TO_TTN = {
    "Sensor:s1": os.environ.get("SENSOR_S1_DEVICE", "lopy4-salon"),
    "Sensor:s2": os.environ.get("SENSOR_S2_DEVICE", "lopy4-dormitorio"),
    "Sensor:s3": os.environ.get("SENSOR_S3_DEVICE", "lopy4-exterior"),
}

# Whitelist NFC: mapeo nombre → UID (últimos 4 caracteres hex).
# Formato en Orion: "nombre1:C3D4,nombre2:BEEF"
# Internamente: {"nombre1": "C3D4", "nombre2": "BEEF"}
NFC_AUTHORIZED_DEFAULT = {"Tarjeta Principal": "C3D4", "Visitante": "BEEF"}
AFORO_MAX      = 5
_log_counter   = int(time.time())

# ============================================================
# HELPERS — Orion
# ============================================================

def _patch(eid, attrs):
    try:
        r = _session.patch(
            f"{ORION}/v2/entities/{eid}/attrs?options=keyValues",
            json=attrs, headers=FS_HEADERS, timeout=5)
        logging.info(f"PATCH {eid} → {r.status_code}")
    except Exception as e:
        logging.error(f"PATCH error {eid}: {e}")


def _post_entity(entity):
    try:
        r = _session.post(
            f"{ORION}/v2/entities",
            json=entity, headers=FS_HEADERS, timeout=5)
        logging.info(f"POST {entity.get('id','')} → {r.status_code}")
    except Exception as e:
        logging.error(f"POST error: {e}")


def _update_attrs(eid, datos):
    """Actualiza atributos escalares del sensor en Orion vía PATCH keyValues.
    Filtra objetos anidados y duplicados con sufijo de canal Cayenne LPP (_N)."""
    attrs = {}
    for k, v in datos.items():
        if isinstance(v, (dict, list)):
            continue
        if k == "raw_hex":
            continue
        # Los sufijos _N son duplicados del decodificador Cayenne LPP (temperature_1, humidity_2…)
        if re.search(r'_\d+$', k):
            continue
        attrs[k] = v
    attrs["timestamp"] = datetime.now(timezone.utc).isoformat()
    try:
        r = _session.patch(
            f"{ORION}/v2/entities/{eid}/attrs?options=keyValues",
            json=attrs, headers=FS_HEADERS, timeout=5)
        if r.status_code in (200, 204):
            logging.info(f"UPDATE {eid} → {r.status_code}")
        else:
            logging.error(f"UPDATE {eid} → {r.status_code}: {r.text[:300]}")
    except Exception as e:
        logging.error(f"UPDATE error {eid}: {e}")


def _alerta(tipo, active, msg, severity, sid=""):
    _patch(f"Alert:{tipo}", {
        "active":    active,
        "message":   msg,
        "severity":  severity,
        "refSensor": sid,
        "timestamp": datetime.now(timezone.utc).isoformat()
    })


# ============================================================
# HELPERS — TTN Downlink
# ============================================================

def _downlink(sensor_id, bytes_list):
    device = SENSOR_TO_TTN.get(sensor_id)
    if not device:
        return
    if "XXXXXXXXXX" in TTN_API_KEY:
        logging.warning(f"TTN_API_KEY no configurada — downlink omitido")
        return

    url  = f"{TTN_API_BASE}/as/applications/{TTN_APP_ID}/devices/{device}/down/push"
    hdrs = {
        "Authorization": f"Bearer {TTN_API_KEY}",
        "Content-Type":  "application/json"
    }
    body = {"downlinks": [{
        "f_port":      1,
        "frm_payload": base64.b64encode(bytes(bytes_list)).decode(),
        "priority":    "NORMAL"
    }]}
    try:
        r = _session.post(url, json=body, headers=hdrs, timeout=5)
        logging.info(f"Downlink {device} {bytes_list} → {r.status_code}")
    except Exception as e:
        logging.error(f"Downlink error {device}: {e}")


def _normalize_uid(uid):
    """Normaliza UID a 4 caracteres hex (últimos 4 dígitos).
    Retorna 4 caracteres en mayúscula, o None si es inválido."""
    try:
        cleaned = ''.join(c for c in str(uid).upper() if c in '0123456789ABCDEF')
        if len(cleaned) == 0:
            return None
        return cleaned[-4:]  # Últimos 4 caracteres
    except:
        return None


def _parse_nfc_whitelist(whitelist_str):
    """Convierte string "nombre:UID,nombre:UID" a dict {"nombre": "UID"}.
    También migra formato antiguo "UID,UID" generando nombres automáticos.
    Fallback a NFC_AUTHORIZED_DEFAULT si string está vacío o inválido."""
    if not whitelist_str:
        return NFC_AUTHORIZED_DEFAULT.copy()

    try:
        wl_dict = {}
        tarjeta_counter = 1

        for pair in whitelist_str.split(','):
            pair = pair.strip()
            if not pair:
                continue

            # Formato nuevo: "nombre:UID"
            if ':' in pair:
                nombre, uid = pair.split(':', 1)
                nombre = nombre.strip()
                uid = uid.strip().upper()
                if nombre and len(uid) == 4 and all(c in '0123456789ABCDEF' for c in uid):
                    wl_dict[nombre] = uid
            # Formato antiguo: solo "UID" (migración automática)
            else:
                uid = pair.upper()
                if len(uid) == 4 and all(c in '0123456789ABCDEF' for c in uid):
                    nombre = f"Tarjeta {tarjeta_counter}"
                    wl_dict[nombre] = uid
                    tarjeta_counter += 1

        return wl_dict if wl_dict else NFC_AUTHORIZED_DEFAULT.copy()
    except Exception as e:
        logging.error(f"Error parseando whitelist: {e}")
        return NFC_AUTHORIZED_DEFAULT.copy()


def _serialize_nfc_whitelist(wl_dict):
    """Convierte dict {"nombre": "UID"} a string "nombre:UID,nombre:UID"."""
    if not wl_dict:
        return ""
    pairs = [f"{nombre}:{uid}" for nombre, uid in sorted(wl_dict.items())]
    return ",".join(pairs)


def _push_whitelist_downlink():
    """Envía la whitelist actual de Orion al LoPy4 dormitorio como downlink 0x08.
    Formato: [0x08][count][uid1_hi][uid1_lo][uid2_hi][uid2_lo]...
    Los UIDs se almacenan como 4 caracteres hex (16 bits).
    Máximo 24 UIDs por limitación del payload LoRaWAN (51 bytes disponibles).
    """
    try:
        r = _session.get(
            f"{ORION}/v2/entities/Sensor:s2/attrs/nfcAuthorizedUIDs/value",
            headers={k: v for k, v in FS_HEADERS.items() if k != 'Content-Type'},
            timeout=5)
        if r.status_code != 200:
            logging.warning("No se pudo leer nfcAuthorizedUIDs de Orion")
            wl_dict = NFC_AUTHORIZED_DEFAULT.copy()
        else:
            wl_str = r.text.strip().strip('"')
            wl_dict = _parse_nfc_whitelist(wl_str)
    except Exception as e:
        logging.error(f"_push_whitelist_downlink: error leyendo UIDs: {e}")
        wl_dict = NFC_AUTHORIZED_DEFAULT.copy()

    if not wl_dict:
        logging.info("Whitelist vacía, no se envía downlink")
        return

    payload = [0x08, 0]  # Comando 0x08, count se actualiza después
    valid_count = 0

    for nombre, uid in sorted(wl_dict.items())[:24]:
        try:
            val = int(uid, 16)
            if val > 0xFFFF:
                logging.warning(f"UID {uid} ('{nombre}') fuera de rango, descartado")
                continue
            payload.append((val >> 8) & 0xFF)
            payload.append(val & 0xFF)
            valid_count += 1
        except ValueError:
            logging.warning(f"UID inválido '{uid}' ('{nombre}'), descartado")
            continue

    payload[1] = valid_count
    if valid_count > 0:
        _downlink("Sensor:s2", payload)
        logging.info(f"Whitelist sync downlink enviado: {valid_count} UIDs ('{', '.join(list(wl_dict.keys())[:5])}')")


# ============================================================
# REGLAS DE AUTOMATIZACIÓN
# ============================================================

def r_temp_alta(d, sid):
    t = d.get("temperature")
    if t is None:
        return
    if t > 28:
        logging.warning(f"Temp alta {t}C en {sid}")
        _alerta("temp_high", True, f"Temperatura alta: {t}C", "warning", sid)
        _downlink(sid, [0x06, 0x01])
        _led_manager.add_alert(sid, "temp")
    else:
        _alerta("temp_high", False, "", "info", sid)
        _downlink(sid, [0x06, 0x02])
        _led_manager.remove_alert(sid, "temp")


def r_temp_baja(d, sid):
    t = d.get("temperature")
    if t is None:
        return
    if t < 10:
        logging.warning(f"Temp baja {t}C en {sid}")
        _alerta("temp_low", True, f"Temperatura baja: {t}C", "warning", sid)
        _downlink(sid, [0x06, 0x00])
        _led_manager.add_alert(sid, "temp")
    else:
        _alerta("temp_low", False, "", "info", sid)
        _downlink(sid, [0x06, 0x02])
        _led_manager.remove_alert(sid, "temp")


def r_humedad(d, sid):
    h = d.get("humidity")
    if h is None:
        return
    if h > 80:
        logging.warning(f"Humedad alta {h}% en {sid}")
        _alerta("humidity", True, f"Humedad excesiva: {h}%", "warning", sid)
        _downlink(sid, [0x06, 0x03])
        _led_manager.add_alert(sid, "humidity")
    else:
        _alerta("humidity", False, "", "info", sid)
        _downlink(sid, [0x06, 0x02])
        _led_manager.remove_alert(sid, "humidity")


def r_vibracion(d, sid):
    vibration_detected = d.get("vibrationDetected", False)
    if vibration_detected:
        mag = d.get("accelerationMagnitude", 0)
        logging.warning(f"Vibracion {mag:.2f}g en {sid}")
        _alerta("vibration", True, f"Vibracion: {mag:.2f}g", "critical", sid)
        _downlink(sid, [0x01, 255, 0, 255])
        _led_manager.add_alert(sid, "vibration")
    else:
        _alerta("vibration", False, "", "info", sid)
        _downlink(sid, [0x01, 0, 255, 0])
        _led_manager.remove_alert(sid, "vibration")


def r_nfc(d, sid):
    nfc_detected = d.get("nfcDetected", False)
    uid_partial = int(round(d.get("nfcUidPartial", 0) * 100)) if nfc_detected else 0
    uid = f"{uid_partial:04X}"

    logging.info(f"NFC evento: detected={nfc_detected} UID={uid} sid={sid}")

    if not nfc_detected:
        logging.debug(f"Lectura NFC sin resultado en {sid}")
        return

    if uid == "0000":
        logging.debug(f"Lectura NFC vacía en {sid} (UID=0x0000)")
        return

    # Obtener whitelist y buscar alias del UID
    try:
        r = _session.get(
            f"{ORION}/v2/entities/Sensor:s2/attrs/nfcAuthorizedUIDs/value",
            headers={k:v for k,v in FS_HEADERS.items() if k != 'Content-Type'},
            timeout=5)
        if r.status_code == 200:
            wl_str = r.text.strip().strip('"')
            wl_dict = _parse_nfc_whitelist(wl_str)
        else:
            wl_dict = NFC_AUTHORIZED_DEFAULT.copy()
    except Exception as e:
        logging.warning(f"Error leyendo whitelist NFC: {e}")
        wl_dict = NFC_AUTHORIZED_DEFAULT.copy()

    # Buscar alias (nombre) del UID
    uid_alias = None
    for nombre, stored_uid in wl_dict.items():
        if stored_uid == uid:
            uid_alias = nombre
            break

    authorized = uid_alias is not None
    log_display = f"'{uid_alias}'" if uid_alias else f"UID={uid}"
    logging.info(f"NFC {log_display} authorized={authorized}")

    global _log_counter
    _log_counter += 1
    _post_entity({
        "id":         f"AccessLog:{_log_counter}",
        "type":       "AccessLog",
        "nfcUID":     {"type": "Text",         "value": uid_alias or uid},
        "authorized": {"type": "Boolean",      "value": authorized},
        "refSensor":  {"type": "Relationship", "value": sid},
        "timestamp":  {"type": "DateTime",     "value": datetime.now(timezone.utc).isoformat()}
    })

    if authorized:
        _alerta("nfc_denied", False, "", "info", sid)
        _downlink(sid, [0x03])
        _led_manager.remove_alert(sid, "nfc_denied")
    else:
        _alerta("nfc_denied", True, f"Acceso denegado {log_display}", "critical", sid)
        _downlink(sid, [0x04])
        _led_manager.add_alert(sid, "nfc_denied")


def r_aforo(d, sid):
    n = d.get("bleDevicesNearby")
    if n is None:
        return
    if n > AFORO_MAX:
        logging.warning(f"Aforo superado: {n} BLE en {sid}")
        _alerta("aforo", True, f"Aforo: {n} dispositivos BLE", "warning", sid)
        _downlink(sid, [0x05, 0x01])
    else:
        _alerta("aforo", False, "", "info", sid)
        _downlink(sid, [0x05, 0x00])


def r_lux_exterior(d, sid):
    lux = d.get("luminosity")
    if lux is None:
        return
    if lux < 50:
        logging.warning(f"Lux exterior baja: {lux} en {sid}")
        _alerta("lux_low", True, f"Luz baja: {lux} lx", "warning", sid)
        _downlink(sid, [0x07, 0x01])
    else:
        _alerta("lux_low", False, "", "info", sid)
        _downlink(sid, [0x07, 0x00])


def r_presion(d, sid):
    p = d.get("barometricPressure")
    if p is None:
        return
    if p < 950:
        logging.warning(f"Presion baja: {p} hPa en {sid}")
        _alerta("pressure_low", True, f"Presion baja: {p} hPa", "warning", sid)
        _downlink(sid, [0x02, 255, 0, 0])
        _led_manager.add_alert(sid, "pressure")
    else:
        _alerta("pressure_low", False, "", "info", sid)
        _downlink(sid, [0x02, 0, 255, 0])
        _led_manager.remove_alert(sid, "pressure")


TODAS_REGLAS = [
    r_temp_alta, r_temp_baja, r_humedad, r_vibracion,
    r_nfc, r_aforo, r_lux_exterior, r_presion
]

# ============================================================
# ENDPOINTS HTTP
# ============================================================

@app.route("/notify", methods=["POST"])
def notify():
    datos = request.get_json(force=True, silent=True)
    if not datos:
        return jsonify({"error": "payload vacío"}), 400
    logging.info(f"Notificacion sub={datos.get('subscriptionId', '?')}")
    for entidad in datos.get("data", []):
        sid = entidad.get("id", "")
        for regla in TODAS_REGLAS:
            try:
                regla(entidad, sid)
            except Exception as e:
                logging.error(f"Error en regla {regla.__name__}: {e}")
    return jsonify({"status": "ok"}), 200


@app.route("/iot/ul", methods=["POST"])
def iot_webhook():
    """Webhook para TTN uplinks — procesa datos de LoRaWAN y actualiza Orion"""
    payload = request.get_json(force=True, silent=True)
    if not payload:
        return jsonify({"error": "payload vacío"}), 400

    try:
        # Extraer device_id desde TTN webhook format
        device_id = payload.get("end_device_ids", {}).get("device_id", "")
        if not device_id:
            logging.warning("No device_id en webhook TTN")
            return jsonify({"error": "missing device_id"}), 400

        # Mapear device_id (ej. "lopy4-salon") a sensor (ej. "Sensor:s1")
        sensor_map = {v: k for k, v in SENSOR_TO_TTN.items()}
        sensor_id = sensor_map.get(device_id)
        if not sensor_id:
            logging.warning(f"Device {device_id} no mapea a sensor conocido")
            return jsonify({"error": f"unknown device: {device_id}"}), 400

        # Extraer datos decodificados del uplink
        uplink = payload.get("uplink_message", {})
        datos = uplink.get("decoded_payload", {})
        if not datos:
            logging.info(f"Sin decoded_payload para {sensor_id}")
            return jsonify({"status": "ok, no decoded payload"}), 200

        logging.info(f"TTN uplink {sensor_id}: {datos}")

        # Crear/actualizar atributos en Orion
        _update_attrs(sensor_id, datos)

        # Aplicar reglas de automatización
        for regla in TODAS_REGLAS:
            try:
                regla(datos, sensor_id)
            except Exception as e:
                logging.error(f"Error en regla {regla.__name__}: {e}")

        return jsonify({"status": "ok"}), 200

    except Exception as e:
        logging.error(f"Error en /iot/ul: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/health", methods=["GET"])
def health():
    return jsonify({
        "status":    "running",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "orion":     ORION,
        "ttn_app":   TTN_APP_ID,
        "ttn_ready": "XXXXXXXXXX" not in TTN_API_KEY
    }), 200


@app.route("/alerts", methods=["GET"])
def alerts():
    try:
        r = _session.get(
            f"{ORION}/v2/entities?type=Alert&q=active==true&options=keyValues",
            headers={k:v for k,v in FS_HEADERS.items() if k != 'Content-Type'},
            timeout=5)
        return jsonify(r.json()), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/alertas", methods=["GET"])
def api_alertas():
    try:
        r = _session.get(
            f"{ORION}/v2/entities?type=Alert&options=keyValues&limit=100",
            headers={k:v for k,v in FS_HEADERS.items() if k != 'Content-Type'},
            timeout=5)
        data = r.json()
        data.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
        activas  = [a for a in data if a.get("active") is True]
        historial = data[:50]
        return jsonify({"activas": activas, "historial": historial}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/access-log", methods=["GET"])
def api_access_log():
    try:
        r = _session.get(
            f"{ORION}/v2/entities?type=AccessLog&options=keyValues&limit=50",
            headers={k:v for k,v in FS_HEADERS.items() if k != 'Content-Type'},
            timeout=5)
        data = r.json()
        # sort by timestamp desc
        data.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
        return jsonify(data), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/nodos", methods=["GET"])
def api_nodos():
    try:
        r = _session.get(
            f"{ORION}/v2/entities?type=Sensor&options=keyValues",
            headers={k:v for k,v in FS_HEADERS.items() if k != 'Content-Type'},
            timeout=5)
        return jsonify(r.json()), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/status", methods=["GET"])
def api_status():
    return jsonify({
        "server":    "running",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "orion":     ORION,
        "ttn_app":   TTN_APP_ID,
        "ttn_ready": "XXXXXXXXXX" not in TTN_API_KEY
    }), 200

@app.route("/api/nfc/uids", methods=["GET"])
def api_get_uids():
    try:
        r = _session.get(
            f"{ORION}/v2/entities/Sensor:s2/attrs/nfcAuthorizedUIDs/value",
            headers={k:v for k,v in FS_HEADERS.items() if k != 'Content-Type'},
            timeout=5)
        if r.status_code == 200:
            wl_str = r.text.strip().strip('"')
            wl_dict = _parse_nfc_whitelist(wl_str)
        else:
            wl_dict = NFC_AUTHORIZED_DEFAULT.copy()
    except Exception as e:
        logging.error(f"api_get_uids error: {e}")
        wl_dict = NFC_AUTHORIZED_DEFAULT.copy()

    # Retornar lista de objetos {nombre, uid}
    result = [{"nombre": nombre, "uid": uid} for nombre, uid in sorted(wl_dict.items())]
    return jsonify(result), 200

@app.route("/api/nfc/uids", methods=["POST"])
def api_add_uid():
    data = request.get_json(silent=True) or {}
    nombre = str(data.get("nombre", "")).strip()
    uid = str(data.get("uid", "")).strip()

    if not nombre or nombre == "[object Object]":
        return jsonify({"error": "Nombre de tarjeta requerido y válido"}), 400

    normalized_uid = _normalize_uid(uid)
    if not normalized_uid:
        return jsonify({"error": "UID inválido. Debe ser hexadecimal (0-9, A-F)"}), 400

    try:
        # Retry loop para manejar race conditions
        for attempt in range(3):
            r = _session.get(
                f"{ORION}/v2/entities/Sensor:s2/attrs/nfcAuthorizedUIDs/value",
                headers={k:v for k,v in FS_HEADERS.items() if k != 'Content-Type'},
                timeout=5)

            if r.status_code == 200:
                wl_str = r.text.strip().strip('"')
                wl_dict = _parse_nfc_whitelist(wl_str)
            else:
                wl_dict = NFC_AUTHORIZED_DEFAULT.copy()

            # Verificar si el UID ya existe bajo otro nombre
            for existing_name, existing_uid in wl_dict.items():
                if existing_uid == normalized_uid:
                    logging.info(f"UID {normalized_uid} ya existe como '{existing_name}'")
                    return jsonify({"status": "ok", "message": f"UID ya autorizado como '{existing_name}'",
                                    "data": [{"nombre": n, "uid": u} for n, u in sorted(wl_dict.items())]}), 200

            # Agregar nuevo nombre:UID
            wl_dict[nombre] = normalized_uid
            wl_str = _serialize_nfc_whitelist(wl_dict)
            _patch("Sensor:s2", {"nfcAuthorizedUIDs": {"type": "Text", "value": wl_str}})
            _push_whitelist_downlink()

            logging.info(f"Tarjeta '{nombre}' ({normalized_uid}) añadida a la whitelist")
            return jsonify({"status": "ok", "message": "Tarjeta añadida",
                            "data": [{"nombre": n, "uid": u} for n, u in sorted(wl_dict.items())]}), 200

        return jsonify({"error": "No se pudo actualizar la whitelist tras 3 intentos"}), 500
    except Exception as e:
        logging.error(f"api_add_uid error: {e}")
        return jsonify({"error": str(e)}), 500

@app.route("/api/nfc/uids/<nombre>", methods=["DELETE"])
def api_delete_uid(nombre):
    nombre = str(nombre).strip() if nombre else ""
    if not nombre or nombre == "[object Object]":
        return jsonify({"error": "Nombre de tarjeta inválido"}), 400

    try:
        # Retry loop para manejar race conditions
        for attempt in range(3):
            r = _session.get(
                f"{ORION}/v2/entities/Sensor:s2/attrs/nfcAuthorizedUIDs/value",
                headers={k:v for k,v in FS_HEADERS.items() if k != 'Content-Type'},
                timeout=5)

            if r.status_code == 200:
                wl_str = r.text.strip().strip('"')
                wl_dict = _parse_nfc_whitelist(wl_str)
            else:
                wl_dict = NFC_AUTHORIZED_DEFAULT.copy()

            if nombre not in wl_dict:
                logging.warning(f"Tarjeta '{nombre}' no encontrada en whitelist")
                return jsonify({"status": "ok", "message": "Tarjeta no encontrada",
                                "data": [{"nombre": n, "uid": u} for n, u in sorted(wl_dict.items())]}), 200

            del wl_dict[nombre]
            wl_str = _serialize_nfc_whitelist(wl_dict)
            _patch("Sensor:s2", {"nfcAuthorizedUIDs": {"type": "Text", "value": wl_str}})
            _push_whitelist_downlink()

            logging.info(f"Tarjeta '{nombre}' eliminada de la whitelist")
            return jsonify({"status": "ok", "message": "Tarjeta eliminada",
                            "data": [{"nombre": n, "uid": u} for n, u in sorted(wl_dict.items())]}), 200

        return jsonify({"error": "No se pudo actualizar la whitelist tras 3 intentos"}), 500
    except Exception as e:
        logging.error(f"api_delete_uid error: {e}")
        return jsonify({"error": str(e)}), 500

@app.route("/api/nfc/sync", methods=["POST"])
def api_nfc_sync():
    """Fuerza sincronización explícita de la whitelist al LoPy4 dormitorio"""
    try:
        _push_whitelist_downlink()
        return jsonify({"status": "ok", "message": "Sincronización de whitelist NFC iniciada"}), 200
    except Exception as e:
        logging.error(f"api_nfc_sync error: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/led/<nodo>", methods=["POST"])
def api_led(nodo):
    data = request.get_json(silent=True) or {}
    comando = data.get("comando", "color")
    r = data.get("r", 0)
    g = data.get("g", 0)
    b = data.get("b", 0)
    cmd_byte = 0x01 if comando == "color" else 0x02
    _downlink(f"Sensor:{nodo}", [cmd_byte, r, g, b])
    return jsonify({"status": "ok"}), 200

if __name__ == "__main__":
    logging.info("Servidor iniciando en puerto 5000...")
    logging.info(f"Orion: {ORION}")
    logging.info(f"TTN App: {TTN_APP_ID}")
    if "XXXXXXXXXX" in TTN_API_KEY:
        logging.warning("TTN_API_KEY no configurada — downlinks desactivados")

    _init_ble_client()

    app.run(host="0.0.0.0", port=5000, debug=False, threaded=True)
