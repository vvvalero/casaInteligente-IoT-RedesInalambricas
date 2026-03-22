#!/usr/bin/env python3
# notification_server.py — Servidor de automatización Casa Inteligente IoT
# Reglas: temp alta/baja, humedad, vibración, NFC, aforo BLE, luminosidad exterior, presión
# Acciones: actualizar Orion + downlink TTN API automático

from flask import Flask, request, jsonify
import requests, json, logging, base64, time
from datetime import datetime, timezone

app = Flask(__name__)
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s [%(levelname)s] %(message)s')

# ============================================================
# CONFIG — editar antes de usar
# ============================================================
ORION      = "http://localhost:1026"
FS_HEADERS = {"Content-Type":"application/json",
              "fiware-service":"smarthome","fiware-servicepath":"/"}

TTN_APP_ID   = "casa-inteligente-iot"
TTN_API_KEY  = "NNSXS.XXXXXXXXXX"   # TTN Console → API keys
TTN_API_BASE = "https://eu1.cloud.thethings.network/api/v3"

SENSOR_TO_TTN = {
    "Sensor:s1": "lopy4-salon",
    "Sensor:s2": "lopy4-dormitorio",
    "Sensor:s3": "lopy4-exterior",
}
NFC_AUTHORIZED = {"A1B2C3D4", "DEADBEEF"}
AFORO_MAX = 5
_log_counter = int(time.time())

# ============================================================
# HELPERS
# ============================================================
def _patch(eid, attrs):
    try:
        r = requests.patch(f"{ORION}/v2/entities/{eid}/attrs?options=keyValues",
                           json=attrs, headers=FS_HEADERS, timeout=5)
        logging.info(f"PATCH {eid} → {r.status_code}")
    except Exception as e:
        logging.error(f"PATCH error {eid}: {e}")

def _post_entity(entity):
    try:
        r = requests.post(f"{ORION}/v2/entities", json=entity, headers=FS_HEADERS, timeout=5)
        logging.info(f"POST {entity.get('id','')} → {r.status_code}")
    except Exception as e:
        logging.error(f"POST error: {e}")

def _alerta(tipo, active, msg, severity, sid=""):
    _patch(f"Alert:{tipo}", {"active":active,"message":msg,
           "severity":severity,"refSensor":sid,
           "timestamp":datetime.now(timezone.utc).isoformat()})

def _downlink(sensor_id, bytes_list):
    device = SENSOR_TO_TTN.get(sensor_id)
    if not device: return
    url = f"{TTN_API_BASE}/as/applications/{TTN_APP_ID}/devices/{device}/down/push"
    hdrs = {"Authorization":f"Bearer {TTN_API_KEY}","Content-Type":"application/json"}
    body = {"downlinks":[{"f_port":1,
            "frm_payload":base64.b64encode(bytes(bytes_list)).decode(),
            "priority":"NORMAL"}]}
    try:
        r = requests.post(url, json=body, headers=hdrs, timeout=5)
        logging.info(f"Downlink {device} {bytes_list} → {r.status_code}")
    except Exception as e:
        logging.error(f"Downlink error {device}: {e}")

# ============================================================
# REGLAS
# ============================================================
def r_temp_alta(d, sid):
    t = d.get("temperature")
    if t is None or t <= 28: return
    logging.warning(f"Temp alta {t}C en {sid}")
    _alerta("temp_high", True, f"Temperatura alta: {t}C", "warning", sid)
    _downlink(sid, [0x06, 0x01])   # LED naranja

def r_temp_baja(d, sid):
    t = d.get("temperature")
    if t is None or t >= 10: return
    logging.warning(f"Temp baja {t}C en {sid}")
    _alerta("temp_low", True, f"Temperatura baja: {t}C", "warning", sid)
    _downlink(sid, [0x06, 0x00])   # LED azul

def r_humedad(d, sid):
    h = d.get("humidity")
    if h is None or h <= 80: return
    logging.warning(f"Humedad alta {h}% en {sid}")
    _alerta("humidity", True, f"Humedad excesiva: {h}%", "warning", sid)

def r_vibracion(d, sid):
    if not d.get("vibrationDetected", False): return
    mag = d.get("accelerationMagnitude", 0)
    logging.warning(f"Vibracion {mag:.2f}g en {sid}")
    _alerta("vibration", True, f"Vibracion: {mag:.2f}g", "critical", sid)
    _downlink(sid, [0x01, 255, 0, 255])   # LED magenta

def r_nfc(d, sid):
    if not d.get("nfcDetected", False): return
    uid_partial = d.get("nfcUidPartial", 0)
    uid = f"{uid_partial:08X}"
    # Obtener UIDs autorizados de Orion
    try:
        rr = requests.get(f"{ORION}/v2/entities/Sensor:s2/attrs/nfcAuthorizedUIDs/value",
                          headers={k:v for k,v in FS_HEADERS.items() if k!='Content-Type'}, timeout=3)
        uids = set(rr.text.strip().strip('"').split(',')) if rr.status_code == 200 else NFC_AUTHORIZED
    except Exception:
        uids = NFC_AUTHORIZED
    authorized = uid in uids
    logging.info(f"NFC UID={uid} authorized={authorized}")
    # Crear AccessLog
    global _log_counter
    _log_counter += 1
    _post_entity({"id":f"AccessLog:{_log_counter}","type":"AccessLog",
                  "nfcUID":{"type":"Text","value":uid},
                  "authorized":{"type":"Boolean","value":authorized},
                  "refSensor":{"type":"Relationship","value":sid},
                  "timestamp":{"type":"DateTime","value":datetime.now(timezone.utc).isoformat()}})
    if authorized:
        _alerta("nfc_denied", False, "", "info", sid)
        _downlink(sid, [0x03])   # LED verde
    else:
        _alerta("nfc_denied", True, f"Acceso denegado UID={uid}", "critical", sid)
        _downlink(sid, [0x04])   # LED rojo

def r_aforo(d, sid):
    n = d.get("bleDevicesNearby")
    if n is None: return
    if n > AFORO_MAX:
        logging.warning(f"Aforo superado: {n} BLE en {sid}")
        _alerta("aforo", True, f"Aforo: {n} dispositivos BLE", "warning", sid)
        _downlink(sid, [0x05])   # LED amarillo
    else:
        _alerta("aforo", False, "", "info", sid)

def r_lux_exterior(d, sid):
    lux = d.get("luminosity")
    if lux is None or lux >= 50: return
    logging.info(f"Lux exterior baja: {lux} en {sid}")
    _downlink(sid, [0x07])   # LED blanco

def r_presion(d, sid):
    p = d.get("barometricPressure")
    if p is None or p >= 1000: return
    logging.warning(f"Presion baja: {p} hPa en {sid}")
    _alerta("pressure_low", True, f"Presion baja: {p} hPa", "warning", sid)
    _downlink(sid, [0x02, 255, 0, 0])   # LED rojo parpadeante

TODAS_REGLAS = [r_temp_alta, r_temp_baja, r_humedad, r_vibracion,
                r_nfc, r_aforo, r_lux_exterior, r_presion]

# ============================================================
# ENDPOINTS
# ============================================================
@app.route("/notify", methods=["POST"])
def notify():
    datos = request.get_json(force=True, silent=True)
    if not datos:
        return jsonify({"error": "payload vacío"}), 400
    logging.info(f"Notificacion sub={datos.get('subscriptionId','?')}")
    for entidad in datos.get("data", []):
        sid = entidad.get("id", "")
        for regla in TODAS_REGLAS:
            try:
                regla(entidad, sid)
            except Exception as e:
                logging.error(f"Error en regla {regla.__name__}: {e}")
    return jsonify({"status": "ok"}), 200

@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status":"running",
                    "timestamp":datetime.now(timezone.utc).isoformat()}), 200

@app.route("/alerts", methods=["GET"])
def alerts():
    """Alertas activas en Orion."""
    try:
        r = requests.get(f"{ORION}/v2/entities?type=Alert&q=active==true&options=keyValues",
            headers={k:v for k,v in FS_HEADERS.items() if k!='Content-Type'}, timeout=5)
        return jsonify(r.json()), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/access-log", methods=["GET"])
def access_log():
    """Historial de accesos NFC."""
    try:
        r = requests.get(f"{ORION}/v2/entities?type=AccessLog&options=keyValues&limit=50",
            headers={k:v for k,v in FS_HEADERS.items() if k!='Content-Type'}, timeout=5)
        return jsonify(r.json()), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    logging.info("Servidor iniciando en puerto 5000...")
    logging.info("IMPORTANTE: edita TTN_API_KEY y SENSOR_TO_TTN antes de usar downlinks")
    app.run(host="0.0.0.0", port=5000, debug=False)
