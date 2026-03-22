#!/usr/bin/env python3
# notification_server.py
# Servidor HTTP que recibe notificaciones de suscripciones NGSI-v2
# e implementa lógica de automatización de la casa inteligente.
#
# Automatizaciones implementadas:
#   - Temperatura >28°C  → envía comando onOff=ON al AC de esa habitación
#   - Temperatura <18°C  → envía comando heatCool=HEAT al AC
#   - Presencia + luz<30 → envía comando onOff=ON a la lámpara
#   - Humedad >80%       → log de alerta (ventilación manual)
#
# Dependencias: pip install flask requests
# Uso:          python3 notification_server.py

from flask import Flask, request, jsonify
import requests
import json
import logging
from datetime import datetime

app = Flask(__name__)
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s [%(levelname)s] %(message)s')

# ---- Configuración ----
ORION       = "http://localhost:1026"
FS_HEADERS  = {
    "Content-Type":    "application/json",
    "fiware-service":  "smarthome",
    "fiware-servicepath": "/"
}

# Mapa sensor → lámpara y AC correspondientes
# Sensor s1 → Lamp lamp1, AC ac1 (salón)  etc.
SENSOR_A_LAMP = {
    "Sensor:s1": "Lamp:lamp1",
    "Sensor:s2": "Lamp:lamp2",
    "Sensor:s3": "Lamp:lamp3",
    "Sensor:s4": "Lamp:lamp4",
    "Sensor:s5": "Lamp:lamp5",
}
SENSOR_A_AC = {
    "Sensor:s1": "AC:ac1",
    "Sensor:s2": "AC:ac2",
    "Sensor:s3": "AC:ac3",
    "Sensor:s4": "AC:ac4",
    "Sensor:s5": "AC:ac5",
}


def patch_actuador(entity_id, atributos):
    """Envía un PATCH a Orion para actualizar atributos de un actuador."""
    url = f"{ORION}/v2/entities/{entity_id}/attrs?options=keyValues"
    try:
        r = requests.patch(url, json=atributos, headers=FS_HEADERS, timeout=5)
        logging.info(f"PATCH {entity_id} → HTTP {r.status_code} | {atributos}")
    except Exception as e:
        logging.error(f"Error PATCH {entity_id}: {e}")


def procesar_notificacion(datos):
    """
    Analiza los datos de la notificación y ejecuta automatizaciones.
    """
    sub_id   = datos.get("subscriptionId", "?")
    entities = datos.get("data", [])

    for entidad in entities:
        eid  = entidad.get("id", "")
        tipo = entidad.get("type", "")

        logging.info(f"Notificación sub={sub_id} | {eid}")

        temp      = entidad.get("temperature")
        humidity  = entidad.get("humidity")
        luminosity= entidad.get("luminosity")
        presence  = entidad.get("presence")

        # --- Regla 1: Temperatura alta → encender AC en modo frío ---
        if temp is not None and temp > 28:
            ac_id = SENSOR_A_AC.get(eid)
            if ac_id:
                logging.info(f"  🌡️  Temp alta ({temp}°C) → AC {ac_id} COOL ON")
                patch_actuador(ac_id, {"onOff": "ON", "heatCool": "COOL"})

        # --- Regla 2: Temperatura baja → encender AC en modo calor ---
        if temp is not None and temp < 18:
            ac_id = SENSOR_A_AC.get(eid)
            if ac_id:
                logging.info(f"  🌡️  Temp baja ({temp}°C) → AC {ac_id} HEAT ON")
                patch_actuador(ac_id, {"onOff": "ON", "heatCool": "HEAT"})

        # --- Regla 3: Presencia detectada + poca luz → encender lámpara ---
        if presence == 1 and luminosity is not None and luminosity < 30:
            lamp_id = SENSOR_A_LAMP.get(eid)
            if lamp_id:
                logging.info(f"  💡 Presencia + luz baja ({luminosity}%) → Lamp {lamp_id} ON")
                patch_actuador(lamp_id, {"onOff": "ON"})

        # --- Regla 4: Humedad excesiva → alerta log ---
        if humidity is not None and humidity > 80:
            room = entidad.get("refRoom", "desconocida")
            logging.warning(f"  💧 Humedad alta ({humidity}%) en {room} - revisar ventilación")


# -------------------------------------------------------
# Endpoint de notificaciones
# -------------------------------------------------------
@app.route("/notify", methods=["POST"])
def notify():
    datos = request.get_json(force=True, silent=True)
    if not datos:
        return jsonify({"error": "payload vacío"}), 400

    logging.info("=" * 60)
    logging.info(f"Notificación recibida: {json.dumps(datos, indent=2)}")
    procesar_notificacion(datos)

    return jsonify({"status": "ok"}), 200


# -------------------------------------------------------
# Endpoint de salud
# -------------------------------------------------------
@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "running",
                    "timestamp": datetime.utcnow().isoformat()}), 200


if __name__ == "__main__":
    logging.info("Servidor de notificaciones iniciando en puerto 5000...")
    app.run(host="0.0.0.0", port=5000, debug=False)
