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
import requests, json, logging, base64, time, os, re, asyncio, threading, hashlib
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
retry_strategy = Retry(
    total=3,
    status_forcelist=[500, 502, 503, 504],
    allowed_methods=["GET", "POST", "PATCH"],
    backoff_factor=0.5
)
adapter = HTTPAdapter(max_retries=retry_strategy, pool_connections=20, pool_maxsize=20)
_session.mount("http://", adapter)
_session.mount("https://", adapter)

# Downlink queue: procesa downlinks secuencialmente para evitar rate limiting
_downlink_queue = []
_downlink_queue_lock = threading.Lock()
_downlink_queue_event = threading.Event()
_DOWNLINK_DELAY_MS = 300  # Delay entre downlinks consecutivos

# Estado de alertas por sensor: {(sensor_id, alert_key): bool}
# Permite enviar downlink solo cuando el estado cambia, no en cada uplink.
_alert_states: dict = {}

# Deduplicación de /notify: evita procesar la misma lectura N veces por las N suscripciones de Orion
_notify_last_ts: dict = {}   # {sensor_id: tiempo epoch}
_notify_last_ts_lock = threading.Lock()
_NOTIFY_DEDUP_WINDOW = 2.0   # segundos — ventana dentro de la cual se considera la misma lectura

# Hash de la última whitelist sincronizada al dispositivo dormitorio
_wl_hash_last_sent: str | None = None
_wl_hash_lock = threading.Lock()


def _state_changed(sid: str, key: str, new_val: bool) -> bool:
    """Devuelve True (y actualiza el estado) solo si el valor cambió."""
    k = (sid, key)
    if _alert_states.get(k) == new_val:
        return False
    _alert_states[k] = new_val
    return True

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
    """Inicializa el cliente BLE en un thread.
    Se puede deshabilitar con BLE_DISABLED=1 (útil en DMZ/Docker sin hardware BLE)."""
    global _ble_client
    if os.environ.get("BLE_DISABLED", "").strip() == "1":
        logging.info("[BLE] Deshabilitado por BLE_DISABLED=1")
        return
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

def _send_all_leds(updates):
    """Envía el estado de los 5 indicadores (1-5) en un único downlink 0x0A.
    Formato: [0x0A, s1, s2, s3, s4, s5]
    Cada byte: bits (red_on<<1) | green_on  →  0=apagado 1=verde 2=rojo 3=amarillo"""
    state = [0] * 5
    labels = {0: "apagado", 1: "verde/azul", 2: "rojo/naranja", 3: "amarillo"}
    for led_id, red_on, green_on in updates:
        if 1 <= led_id <= 5:
            state[led_id - 1] = (1 if red_on else 0) << 1 | (1 if green_on else 0)
    _downlink("Sensor:s2", [0x0A] + state)
    logging.info("[LORA] LEDs batch → " + " ".join(
        f"I{i+1}:{labels.get(s, s)}" for i, s in enumerate(state)))

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

        _send_all_leds(led_updates)

    def remove_alert(self, sensor_id, alert_type):
        """Elimina alerta para un nodo/tipo"""
        with self._lock:
            if sensor_id in self.node_alerts:
                self.node_alerts[sensor_id].discard(alert_type)
            if alert_type in self.type_alerts:
                self.type_alerts[alert_type].discard(sensor_id)
            led_updates = self._calculate_led_colors()

        _send_all_leds(led_updates)

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

        # Indicadores 4-5: Alertas por tipo sensor
        alert_leds = {
            "temp":     4,
            "humidity": 5,
        }
        for alert_type, led_id in alert_leds.items():
            if self.type_alerts[alert_type]:
                count = len(self.type_alerts[alert_type])
                if count >= 2:
                    updates.append((led_id, True, True))   # Amarillo (crítico)
                else:
                    updates.append((led_id, True, False))  # Naranja/Rojo (alerta)
            else:
                updates.append((led_id, False, True))      # Azul/Verde (OK)

        # Indicador 6 (NFC) se controla desde r_nfc() vía downlink; no se toca aquí.

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
    # Campos LPP genéricos sin semántica en Orion (son artefactos del primer canal de cada tipo)
    _LPP_GENERIC = {"analogInput", "digitalInput", "raw_hex", "aforoAlerta"}
    attrs = {}
    for k, v in datos.items():
        if isinstance(v, (dict, list)):
            continue
        if k in _LPP_GENERIC:
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


def _ts_z():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def _alerta(tipo, active, msg, severity, sid=""):
    eid = f"Alert:{tipo}"
    ts = _ts_z()
    attrs = {
        "active":    active,
        "message":   msg,
        "severity":  severity,
        "refSensor": sid,
        "timestamp": ts
    }

    # Intentar PATCH primero (entidad ya existe)
    try:
        r = _session.patch(
            f"{ORION}/v2/entities/{eid}/attrs?options=keyValues",
            json=attrs, headers=FS_HEADERS, timeout=5)
        if r.status_code in (200, 204):
            logging.info(f"PATCH {eid} → {r.status_code}")
            return
        elif r.status_code == 404:
            logging.debug(f"Alert {eid} no existe, creando...")
        else:
            logging.error(f"PATCH {eid} → {r.status_code}: {r.text[:300]}")
            return
    except Exception as e:
        logging.error(f"PATCH error {eid}: {e}")
        return

    # Si 404, crear la entidad
    try:
        entity = {
            "id":        eid,
            "type":      "Alert",
            "active":    {"type": "Boolean",   "value": active},
            "message":   {"type": "Text",      "value": msg},
            "severity":  {"type": "Text",      "value": severity},
            "refSensor": {"type": "Relationship", "value": sid},
            "timestamp": {"type": "DateTime",  "value": ts}
        }
        r = _session.post(
            f"{ORION}/v2/entities",
            json=entity, headers=FS_HEADERS, timeout=5)
        if r.status_code in (200, 201):
            logging.info(f"POST {eid} → {r.status_code}")
        else:
            logging.error(f"POST {eid} → {r.status_code}: {r.text[:300]}")
    except Exception as e:
        logging.error(f"POST error {eid}: {e}")


# ============================================================
# HELPERS — TTN Downlink
# ============================================================

def _downlink(sensor_id, bytes_list, replace=False, confirmed=False):
    """Agrega downlink a cola para procesamiento secuencial.
    Deduplicación por (device, comando): comandos distintos coexisten en cola.
    replace=True  → usa /down/replace (borra cola TTN), útil para whitelist sync.
    confirmed=True → TTN pide ACK al device y reintenta automáticamente respetando
                     el duty cycle; ideal para mensajes críticos como la whitelist."""
    device = SENSOR_TO_TTN.get(sensor_id)
    if not device:
        return
    if "XXXXXXXXXX" in TTN_API_KEY:
        logging.warning(f"TTN_API_KEY no configurada — downlink omitido")
        return

    def _cmd_key(payload):
        if not payload:
            return (None, None)
        cmd = payload[0]
        if cmd == 0x09 and len(payload) > 1:
            return (cmd, payload[1])
        return (cmd, None)

    cmd_key = _cmd_key(bytes_list)
    with _downlink_queue_lock:
        for i, (d, bl, _r, _c) in enumerate(_downlink_queue):
            if d == device and _cmd_key(bl) == cmd_key:
                _downlink_queue[i] = (device, bytes_list, replace, confirmed)
                break
        else:
            _downlink_queue.append((device, bytes_list, replace, confirmed))
    _downlink_queue_event.set()


def _downlink_worker():
    """Worker que procesa downlinks de la cola secuencialmente"""
    while True:
        try:
            _downlink_queue_event.wait(timeout=1)
            _downlink_queue_event.clear()

            while True:
                with _downlink_queue_lock:
                    if not _downlink_queue:
                        break
                    device, bytes_list, use_replace, use_confirmed = _downlink_queue.pop(0)

                endpoint = "replace" if use_replace else "push"
                url = f"{TTN_API_BASE}/as/applications/{TTN_APP_ID}/devices/{device}/down/{endpoint}"
                hdrs = {
                    "Authorization": f"Bearer {TTN_API_KEY}",
                    "Content-Type": "application/json"
                }
                downlink_entry = {
                    "f_port": 1,
                    "frm_payload": base64.b64encode(bytes(bytes_list)).decode(),
                    "priority": "HIGH" if use_confirmed else "NORMAL",
                }
                if use_confirmed:
                    downlink_entry["confirmed"] = True
                body = {"downlinks": [downlink_entry]}
                try:
                    r = _session.post(url, json=body, headers=hdrs, timeout=5)
                    if r.status_code == 429:
                        logging.warning(f"Downlink rate limited (429) para {device}, esperando 10s")
                        time.sleep(10)
                    elif r.status_code not in (200, 202, 204):
                        logging.error(f"Downlink {device} {bytes_list} → {r.status_code}: {r.text[:200]}")
                    else:
                        conf_tag = " [confirmed]" if use_confirmed else ""
                        logging.info(f"Downlink {device} {bytes_list} ({endpoint}){conf_tag} → {r.status_code}")
                except Exception as e:
                    logging.error(f"Downlink error {device}: {e}")

                time.sleep(_DOWNLINK_DELAY_MS / 1000.0)

        except Exception as e:
            logging.error(f"Downlink worker error: {e}")
            time.sleep(1)


def _text_to_uid(text):
    """Convierte texto a UID de 4 caracteres hex.
    Ejemplo: 'hola' → b'hola'.hex() → '686f6c61' → '6c61' (últimos 4)
    Retorna 4 caracteres en mayúscula, o None si es inválido."""
    try:
        if not text or len(text.strip()) == 0:
            return None
        text = text.strip()
        # Convertir a bytes UTF-8 y luego a hex
        hex_str = text.encode('utf-8').hex().upper()
        if len(hex_str) == 0:
            return None
        return hex_str[-4:]  # Últimos 4 caracteres hex
    except:
        return None


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
    Acepta UIDs de cualquier longitud (4 o 8+ caracteres) y usa los últimos 4.
    Devuelve dict vacío si whitelist_str está vacío (no fallback a defaults)."""
    if not whitelist_str or whitelist_str.strip() == "":
        return {}

    try:
        wl_dict = {}
        tarjeta_counter = 1

        for pair in whitelist_str.split(','):
            pair = pair.strip()
            if not pair:
                continue

            # Formato nuevo: "nombre:UID"
            if ':' in pair:
                nombre, uid_raw = pair.split(':', 1)
                nombre = nombre.strip()
                uid_raw = uid_raw.strip().upper()
                # Tomar últimos 4 caracteres si es más largo
                uid = uid_raw[-4:] if len(uid_raw) >= 4 else uid_raw
                if nombre and all(c in '0123456789ABCDEF' for c in uid) and len(uid) == 4:
                    wl_dict[nombre] = uid
            # Formato antiguo: solo "UID" (migración automática)
            else:
                uid_raw = pair.upper()
                # Tomar últimos 4 caracteres si es más largo
                uid = uid_raw[-4:] if len(uid_raw) >= 4 else uid_raw
                if all(c in '0123456789ABCDEF' for c in uid) and len(uid) == 4:
                    nombre = f"Tarjeta {tarjeta_counter}"
                    wl_dict[nombre] = uid
                    tarjeta_counter += 1

        return wl_dict
    except Exception as e:
        logging.error(f"Error parseando whitelist: {e}")
        return {}


def _serialize_nfc_whitelist(wl_dict):
    """Convierte dict {"nombre": "UID"} a string "nombre:UID,nombre:UID"."""
    if not wl_dict:
        return ""
    pairs = [f"{nombre}:{uid}" for nombre, uid in sorted(wl_dict.items())]
    return ",".join(pairs)


def _push_whitelist_downlink(force=False):
    """Envía la whitelist actual de Orion al LoPy4 dormitorio como downlink 0x08.
    Formato: [0x08][count][uid1_hi][uid1_lo][uid2_hi][uid2_lo]...
    Los UIDs se almacenan como 4 caracteres hex (16 bits).
    Máximo 24 UIDs por limitación del payload LoRaWAN (51 bytes disponibles).

    Solo envía si la whitelist cambió desde el último sync (hash tracking).
    force=True omite la comprobación de hash (útil para sync manual explícito).
    El downlink se marca como confirmed para que TTN gestione los reintentos
    automáticamente respetando el duty cycle del gateway."""
    global _wl_hash_last_sent

    try:
        r = _session.get(
            f"{ORION}/v2/entities/Sensor:s2/attrs/nfcAuthorizedUIDs/value",
            headers={k: v for k, v in FS_HEADERS.items() if k != 'Content-Type'},
            timeout=5)
        if r.status_code != 200:
            logging.warning("No se pudo leer nfcAuthorizedUIDs de Orion")
            wl_dict = {}
        else:
            try:
                data = r.json()
                wl_str = data.get("value", "") if isinstance(data, dict) else str(data)
            except:
                wl_str = r.text.strip().strip('"')
            wl_dict = _parse_nfc_whitelist(wl_str)
    except Exception as e:
        logging.error(f"_push_whitelist_downlink: error leyendo UIDs: {e}")
        wl_dict = {}

    if not wl_dict:
        logging.warning("_push_whitelist_downlink: whitelist vacía en Orion, no se envía downlink")
        return 0

    # Calcular hash de la whitelist actual
    wl_hash = hashlib.md5(str(sorted(wl_dict.items())).encode()).hexdigest()

    with _wl_hash_lock:
        if not force and wl_hash == _wl_hash_last_sent:
            logging.debug("Whitelist sin cambios desde último sync, downlink omitido")
            return 0

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
        _downlink("Sensor:s2", payload, replace=True, confirmed=True)
        with _wl_hash_lock:
            _wl_hash_last_sent = wl_hash
        logging.info(f"Whitelist sync downlink enviado: {valid_count} UIDs ('{', '.join(list(wl_dict.keys())[:5])}') [confirmed]")
    return valid_count


# ============================================================
# REGLAS DE AUTOMATIZACIÓN
# ============================================================

def r_temp(d, sid):
    t = d.get("temperature")
    if t is None:
        return

    temp_high = t > 28
    temp_low = t < 10

    prev_high = _alert_states.get((sid, "temp_high"), False)
    prev_low = _alert_states.get((sid, "temp_low"), False)

    if temp_high:
        logging.warning(f"Temp alta {t}C en {sid}")
        _alerta("temp_high", True, f"Temperatura alta: {t}C", "warning", sid)
        if _state_changed(sid, "temp_high", True):
            _downlink(sid, [0x06, 0x01])

        _alerta("temp_low", False, "", "info", sid)
        _state_changed(sid, "temp_low", False)
        _led_manager.add_alert(sid, "temp")

    elif temp_low:
        logging.warning(f"Temp baja {t}C en {sid}")
        _alerta("temp_low", True, f"Temperatura baja: {t}C", "warning", sid)
        if _state_changed(sid, "temp_low", True):
            _downlink(sid, [0x06, 0x00])

        _alerta("temp_high", False, "", "info", sid)
        _state_changed(sid, "temp_high", False)
        _led_manager.add_alert(sid, "temp")

    else:
        _alerta("temp_high", False, "", "info", sid)
        _alerta("temp_low", False, "", "info", sid)

        cleared = False
        if _state_changed(sid, "temp_high", False):
            cleared = True
        if _state_changed(sid, "temp_low", False):
            cleared = True

        if prev_high or prev_low or cleared:
            _downlink(sid, [0x06, 0x02])

        _led_manager.remove_alert(sid, "temp")


def r_humedad(d, sid):
    h = d.get("humidity")
    if h is None:
        return
    if h > 80:
        logging.warning(f"Humedad alta {h}% en {sid}")
        _alerta("humidity", True, f"Humedad excesiva: {h}%", "warning", sid)
        if _state_changed(sid, "humidity", True):
            _downlink(sid, [0x06, 0x03])
        _led_manager.add_alert(sid, "humidity")
    else:
        _alerta("humidity", False, "", "info", sid)
        if _state_changed(sid, "humidity", False):
            _downlink(sid, [0x06, 0x02])
        _led_manager.remove_alert(sid, "humidity")


def r_vibracion(d, sid):
    vibration_detected = d.get("vibrationDetected", False)
    if vibration_detected:
        mag = d.get("accelerationMagnitude", 0)
        logging.warning(f"Vibracion {mag:.2f}g en {sid}")
        _alerta("vibration", True, f"Vibracion: {mag:.2f}g", "critical", sid)
        if _state_changed(sid, "vibration", True):
            _downlink(sid, [0x01, 255, 0, 255])
        _led_manager.add_alert(sid, "vibration")
    else:
        _alerta("vibration", False, "", "info", sid)
        if _state_changed(sid, "vibration", False):
            _downlink(sid, [0x01, 0, 255, 0])
        _led_manager.remove_alert(sid, "vibration")


def r_nfc(d, sid):
    # El UID se codifica como analogInput en el dormitorio (CH4).
    # TTN puede usar distintos nombres según el formateador; se prueban en orden de preferencia.
    analog_val = (d.get("nfcUidPartial")   # formatter semántico personalizado
               or d.get("analogInput_4")   # CayenneLPP con número de canal
               or d.get("analog_in_4")     # CayenneLPP TTN v3
               or d.get("analogInput")     # CayenneLPP sin canal
               or d.get("analog_in"))      # CayenneLPP TTN v3 sin canal

    if analog_val is None:
        logging.debug(f"[NFC] Sin campo analogInput en {sid} — posibles claves: {list(d.keys())}")
        return

    # El valor llega como float (e.g. -56.06); recuperar los 16 bits originales
    uid_partial = int(round(float(analog_val) * 100))
    uid = f"{uid_partial & 0xFFFF:04X}"

    if uid == "0000":
        logging.debug(f"[NFC] Sin tarjeta en {sid}")
        return

    logging.info(f"[NFC] TARJETA DETECTADA: UID={uid} en {sid}")

    # Obtener whitelist y buscar alias del UID
    try:
        r = _session.get(
            f"{ORION}/v2/entities/Sensor:s2/attrs/nfcAuthorizedUIDs/value",
            headers={k:v for k,v in FS_HEADERS.items() if k != 'Content-Type'},
            timeout=5)
        if r.status_code == 200:
            try:
                data = r.json()
                wl_str = data.get("value", "") if isinstance(data, dict) else str(data)
            except:
                wl_str = r.text.strip().strip('"')
            wl_dict = _parse_nfc_whitelist(wl_str)
        else:
            wl_dict = {}
    except Exception as e:
        logging.warning(f"Error leyendo whitelist NFC: {e}")
        wl_dict = {}

    # Buscar alias (nombre) del UID
    uid_alias = None
    for nombre, stored_uid in wl_dict.items():
        if stored_uid == uid:
            uid_alias = nombre
            break

    authorized = uid_alias is not None
    log_display = f"'{uid_alias}'" if uid_alias else f"UID:{uid}"
    logging.info(f"NFC {log_display} authorized={authorized}")

    global _log_counter
    _log_counter += 1
    _post_entity({
        "id":         f"AccessLog:{_log_counter}",
        "type":       "AccessLog",
        "nfcUID":     {"type": "Text",         "value": uid_alias or uid},
        "authorized": {"type": "Boolean",      "value": authorized},
        "refSensor":  {"type": "Relationship", "value": sid},
        "timestamp":  {"type": "DateTime",     "value": _ts_z()}
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
        if _state_changed(sid, "aforo", True):
            _downlink(sid, [0x05, 0x01])
    else:
        _alerta("aforo", False, "", "info", sid)
        if _state_changed(sid, "aforo", False):
            _downlink(sid, [0x05, 0x00])


def r_lux_exterior(d, sid):
    lux = d.get("luminosity")
    if lux is None:
        return
    if lux < 50:
        logging.warning(f"Lux exterior baja: {lux} en {sid}")
        _alerta("lux_low", True, f"Luz baja: {lux} lx", "warning", sid)
        if _state_changed(sid, "lux_low", True):
            _downlink(sid, [0x07, 0x01])
    else:
        _alerta("lux_low", False, "", "info", sid)
        if _state_changed(sid, "lux_low", False):
            _downlink(sid, [0x07, 0x00])


TODAS_REGLAS = [
    r_temp, r_humedad, r_vibracion,
    r_nfc, r_aforo, r_lux_exterior
]

# Reglas que crean entidades únicas por evento (AccessLog, etc.) y solo deben
# ejecutarse desde el uplink directo, no desde suscripciones de Orion.
REGLAS_SOLO_UPLINK = {r_nfc}

# ============================================================
# ENDPOINTS HTTP
# ============================================================

@app.route("/notify", methods=["POST"])
def notify():
    datos = request.get_json(force=True, silent=True)
    if not datos:
        return jsonify({"error": "payload vacío"}), 400
    logging.info(f"Notificacion sub={datos.get('subscriptionId', '?')}")
    now = time.time()
    for entidad in datos.get("data", []):
        sid = entidad.get("id", "")
        # Deduplicación: múltiples suscripciones de Orion disparan /notify para la misma
        # lectura. Solo procesamos reglas (y posibles downlinks) una vez por sensor
        # dentro de la ventana de tiempo definida.
        with _notify_last_ts_lock:
            if now - _notify_last_ts.get(sid, 0) < _NOTIFY_DEDUP_WINDOW:
                continue
            _notify_last_ts[sid] = now
        for regla in TODAS_REGLAS:
            if regla in REGLAS_SOLO_UPLINK:
                continue
            try:
                regla(entidad, sid)
            except Exception as e:
                logging.error(f"Error en regla {regla.__name__}: {e}")
    return jsonify({"status": "ok"}), 200


def _process_uplink(payload: dict):
    """Procesa el uplink TTN en segundo plano para no bloquear el webhook."""
    try:
        device_id = payload.get("end_device_ids", {}).get("device_id", "")
        if not device_id:
            return

        sensor_map = {v: k for k, v in SENSOR_TO_TTN.items()}
        sensor_id = sensor_map.get(device_id)
        if not sensor_id:
            logging.warning(f"Device {device_id} no mapea a sensor conocido")
            return

        uplink = payload.get("uplink_message", {})
        datos = uplink.get("decoded_payload", {})
        if not datos:
            logging.info(f"Sin decoded_payload para {sensor_id}")
            return

        logging.info(f"TTN uplink {sensor_id}: {datos}")

        _update_attrs(sensor_id, datos)

        for regla in TODAS_REGLAS:
            try:
                regla(datos, sensor_id)
            except Exception as e:
                logging.error(f"Error en regla {regla.__name__}: {e}")

    except Exception as e:
        logging.error(f"Error procesando uplink: {e}")


@app.route("/iot/ul", methods=["POST"])
def iot_webhook():
    """Webhook para TTN uplinks — responde inmediatamente y procesa en segundo plano."""
    payload = request.get_json(force=True, silent=True)
    if not payload:
        return jsonify({"error": "payload vacío"}), 400

    # Validación rápida antes de lanzar el hilo
    device_id = payload.get("end_device_ids", {}).get("device_id", "")
    if not device_id:
        logging.warning("No device_id en webhook TTN")
        return jsonify({"error": "missing device_id"}), 400

    threading.Thread(target=_process_uplink, args=(payload,), daemon=True).start()
    return jsonify({"status": "ok"}), 200


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
            # Orion devuelve {"type":"Text","value":"..."} o simplemente "..."
            try:
                data = r.json()
                wl_str = data.get("value", "") if isinstance(data, dict) else str(data)
            except:
                wl_str = r.text.strip().strip('"')
            wl_dict = _parse_nfc_whitelist(wl_str)
        else:
            # Si Orion devuelve error, devolver lista vacía (no tarjetas por defecto)
            wl_dict = {}
    except Exception as e:
        logging.error(f"api_get_uids error: {e}")
        wl_dict = {}

    # Retornar lista de objetos {nombre, uid}
    result = [{"nombre": nombre, "uid": uid} for nombre, uid in sorted(wl_dict.items())]
    return jsonify(result), 200

@app.route("/api/nfc/uids", methods=["POST"])
def api_add_uid():
    data = request.get_json(silent=True) or {}
    logging.info(f"api_add_uid received data: {data}, raw_data: {request.data}")
    nombre = str(data.get("nombre", "")).strip()
    uid_raw = str(data.get("uid", "")).strip()
    logging.info(f"Parsed: nombre='{nombre}', uid_raw='{uid_raw}'")

    if not nombre or nombre == "[object Object]":
        logging.warning(f"Invalid nombre: '{nombre}'")
        return jsonify({"error": "Nombre de tarjeta requerido y válido"}), 400

    if not uid_raw:
        logging.warning(f"Empty uid_raw: '{uid_raw}'")
        return jsonify({"error": "UID de tarjeta requerido"}), 400

    normalized_uid = _normalize_uid(uid_raw)
    if not normalized_uid:
        return jsonify({"error": "UID inválido. Debe contener caracteres hexadecimales (0-9, A-F)"}), 400

    try:
        # Retry loop para manejar race conditions
        for attempt in range(3):
            r = _session.get(
                f"{ORION}/v2/entities/Sensor:s2/attrs/nfcAuthorizedUIDs/value",
                headers={k:v for k,v in FS_HEADERS.items() if k != 'Content-Type'},
                timeout=5)

            if r.status_code == 200:
                try:
                    data = r.json()
                    wl_str = data.get("value", "") if isinstance(data, dict) else str(data)
                except:
                    wl_str = r.text.strip().strip('"')
                wl_dict = _parse_nfc_whitelist(wl_str)
            else:
                wl_dict = {}

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
                try:
                    data = r.json()
                    wl_str = data.get("value", "") if isinstance(data, dict) else str(data)
                except:
                    wl_str = r.text.strip().strip('"')
                wl_dict = _parse_nfc_whitelist(wl_str)
            else:
                wl_dict = {}

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
        count = _push_whitelist_downlink(force=True)
        if count:
            return jsonify({"status": "ok", "message": f"Whitelist enviada: {count} UIDs"}), 200
        else:
            return jsonify({"status": "error", "message": "Whitelist vacía en Orion — añade tarjetas primero"}), 400
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

# Iniciar el worker de downlinks al importar el módulo — funciona tanto con
# gunicorn (que no ejecuta __main__) como con ejecución directa.
# Con gunicorn -w N se inicia un thread por worker process, lo cual es correcto:
# cada proceso gestiona su propia cola de forma independiente.
_downlink_thread = threading.Thread(target=_downlink_worker, daemon=True, name="downlink-worker")
_downlink_thread.start()
logging.info(f"Downlink worker iniciado (delay={_DOWNLINK_DELAY_MS}ms entre comandos)")

_init_ble_client()

if __name__ == "__main__":
    logging.info("Servidor iniciando en puerto 5000...")
    logging.info(f"Orion: {ORION}")
    logging.info(f"TTN App: {TTN_APP_ID}")
    if "XXXXXXXXXX" in TTN_API_KEY:
        logging.warning("TTN_API_KEY no configurada — downlinks desactivados")

    app.run(host="0.0.0.0", port=5000, debug=False, threaded=True)
