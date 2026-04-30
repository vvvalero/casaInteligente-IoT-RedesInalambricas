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
import requests, json, logging, base64, time, os
from datetime import datetime, timezone

app = Flask(__name__)
CORS(app)
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s [%(levelname)s] %(message)s')

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
TTN_API_KEY  = os.environ.get("TTN_API_KEY", "NNSXS.HYUMPGJHVMNT5PGNUSM4XKLXHVZSS2ZSE3G6A5A.UJOMJV5SBYS5GQZK2FJA6B7XDOSRCIBNL7R5WMUKZWBXDVPLJDWA")
TTN_API_BASE = "https://eu1.cloud.thethings.network/api/v3"

SENSOR_TO_TTN = {
    "Sensor:s1": os.environ.get("SENSOR_S1_DEVICE", "lopy4-salon"),
    "Sensor:s2": os.environ.get("SENSOR_S2_DEVICE", "lopy4-dormitorio"),
    "Sensor:s3": os.environ.get("SENSOR_S3_DEVICE", "lopy4-exterior"),
}

NFC_AUTHORIZED = {"A1B2C3D4", "DEADBEEF"}
AFORO_MAX      = 5
_log_counter   = int(time.time())

# ============================================================
# HELPERS — Orion
# ============================================================

def _patch(eid, attrs):
    try:
        r = requests.patch(
            f"{ORION}/v2/entities/{eid}/attrs?options=keyValues",
            json=attrs, headers=FS_HEADERS, timeout=5)
        logging.info(f"PATCH {eid} → {r.status_code}")
    except Exception as e:
        logging.error(f"PATCH error {eid}: {e}")


def _post_entity(entity):
    try:
        r = requests.post(
            f"{ORION}/v2/entities",
            json=entity, headers=FS_HEADERS, timeout=5)
        logging.info(f"POST {entity.get('id','')} → {r.status_code}")
    except Exception as e:
        logging.error(f"POST error: {e}")


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
        r = requests.post(url, json=body, headers=hdrs, timeout=5)
        logging.info(f"Downlink {device} {bytes_list} → {r.status_code}")
    except Exception as e:
        logging.error(f"Downlink error {device}: {e}")


# ============================================================
# REGLAS DE AUTOMATIZACIÓN
# ============================================================

def r_temp_alta(d, sid):
    t = d.get("temperature")
    if t is None or t <= 28:
        return
    logging.warning(f"Temp alta {t}C en {sid}")
    _alerta("temp_high", True, f"Temperatura alta: {t}C", "warning", sid)
    _downlink(sid, [0x06, 0x01])


def r_temp_baja(d, sid):
    t = d.get("temperature")
    if t is None or t >= 10:
        return
    logging.warning(f"Temp baja {t}C en {sid}")
    _alerta("temp_low", True, f"Temperatura baja: {t}C", "warning", sid)
    _downlink(sid, [0x06, 0x00])


def r_humedad(d, sid):
    h = d.get("humidity")
    if h is None or h <= 80:
        return
    logging.warning(f"Humedad alta {h}% en {sid}")
    _alerta("humidity", True, f"Humedad excesiva: {h}%", "warning", sid)


def r_vibracion(d, sid):
    if not d.get("vibrationDetected", False):
        return
    mag = d.get("accelerationMagnitude", 0)
    logging.warning(f"Vibracion {mag:.2f}g en {sid}")
    _alerta("vibration", True, f"Vibracion: {mag:.2f}g", "critical", sid)
    _downlink(sid, [0x01, 255, 0, 255])


def r_nfc(d, sid):
    if not d.get("nfcDetected", False):
        return
    uid_partial = d.get("nfcUidPartial", 0)
    uid = f"{uid_partial:08X}"

    # Obtener UIDs autorizados de Orion en tiempo real
    try:
        r = requests.get(
            f"{ORION}/v2/entities/Sensor:s2/attrs/nfcAuthorizedUIDs/value",
            headers={k:v for k,v in FS_HEADERS.items() if k != 'Content-Type'},
            timeout=3)
        uids = set(r.text.strip().strip('"').split(',')) if r.status_code == 200 \
               else NFC_AUTHORIZED
    except Exception:
        uids = NFC_AUTHORIZED

    authorized = uid in uids
    logging.info(f"NFC UID={uid} authorized={authorized}")

    global _log_counter
    _log_counter += 1
    _post_entity({
        "id":         f"AccessLog:{_log_counter}",
        "type":       "AccessLog",
        "nfcUID":     {"type": "Text",         "value": uid},
        "authorized": {"type": "Boolean",      "value": authorized},
        "refSensor":  {"type": "Relationship", "value": sid},
        "timestamp":  {"type": "DateTime",     "value": datetime.now(timezone.utc).isoformat()}
    })

    if authorized:
        _alerta("nfc_denied", False, "", "info", sid)
        _downlink(sid, [0x03])
    else:
        _alerta("nfc_denied", True, f"Acceso denegado UID={uid}", "critical", sid)
        _downlink(sid, [0x04])


def r_aforo(d, sid):
    n = d.get("bleDevicesNearby")
    if n is None:
        return
    if n > AFORO_MAX:
        logging.warning(f"Aforo superado: {n} BLE en {sid}")
        _alerta("aforo", True, f"Aforo: {n} dispositivos BLE", "warning", sid)
        _downlink(sid, [0x05])
    else:
        _alerta("aforo", False, "", "info", sid)


def r_lux_exterior(d, sid):
    lux = d.get("luminosity")
    if lux is None or lux >= 50:
        return
    logging.info(f"Lux exterior baja: {lux} en {sid}")
    _downlink(sid, [0x07])


def r_presion(d, sid):
    p = d.get("barometricPressure")
    if p is None or p >= 950:   # 950 hPa umbral para Albacete (~700m altitud)
        return
    logging.warning(f"Presion baja: {p} hPa en {sid}")
    _alerta("pressure_low", True, f"Presion baja: {p} hPa", "warning", sid)
    _downlink(sid, [0x02, 255, 0, 0])


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
        r = requests.get(
            f"{ORION}/v2/entities?type=Alert&q=active==true&options=keyValues",
            headers={k:v for k,v in FS_HEADERS.items() if k != 'Content-Type'},
            timeout=5)
        return jsonify(r.json()), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/alertas", methods=["GET"])
def api_alertas():
    try:
        r = requests.get(
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
        r = requests.get(
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
        r = requests.get(
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
        r = requests.get(
            f"{ORION}/v2/entities/Sensor:s2/attrs/nfcAuthorizedUIDs/value",
            headers={k:v for k,v in FS_HEADERS.items() if k != 'Content-Type'},
            timeout=5)
        if r.status_code == 200:
            uids = r.text.strip().strip('"').split(',')
            uids = [u for u in uids if u]
            return jsonify(uids), 200
        return jsonify(list(NFC_AUTHORIZED)), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/nfc/uids", methods=["POST"])
def api_add_uid():
    data = request.get_json(silent=True) or {}
    uid = data.get("uid", "").strip().upper()
    if not uid:
        return jsonify({"error": "UID is required"}), 400
    try:
        r = requests.get(
            f"{ORION}/v2/entities/Sensor:s2/attrs/nfcAuthorizedUIDs/value",
            headers={k:v for k,v in FS_HEADERS.items() if k != 'Content-Type'},
            timeout=3)
        uids = set(r.text.strip().strip('"').split(',')) if r.status_code == 200 else set(NFC_AUTHORIZED)
        uids.add(uid)
        _patch("Sensor:s2", {"nfcAuthorizedUIDs": {"type": "Text", "value": ",".join(uids)}})
        return jsonify({"status": "ok", "uids": list(uids)}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/nfc/uids/<uid>", methods=["DELETE"])
def api_delete_uid(uid):
    uid = uid.strip().upper()
    try:
        r = requests.get(
            f"{ORION}/v2/entities/Sensor:s2/attrs/nfcAuthorizedUIDs/value",
            headers={k:v for k,v in FS_HEADERS.items() if k != 'Content-Type'},
            timeout=3)
        uids = set(r.text.strip().strip('"').split(',')) if r.status_code == 200 else set(NFC_AUTHORIZED)
        if uid in uids:
            uids.remove(uid)
        _patch("Sensor:s2", {"nfcAuthorizedUIDs": {"type": "Text", "value": ",".join(uids)}})
        return jsonify({"status": "ok", "uids": list(uids)}), 200
    except Exception as e:
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
    app.run(host="0.0.0.0", port=5000, debug=False)
