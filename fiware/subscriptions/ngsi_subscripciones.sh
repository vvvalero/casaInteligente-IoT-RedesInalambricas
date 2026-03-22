#!/bin/bash
# ngsi_subscripciones.sh
# Crea suscripciones NGSI-v2 para automatización de la casa inteligente
#
# Reglas implementadas:
#   1. Alerta de temperatura alta  (>28°C) → notificación HTTP
#   2. Alerta de temperatura baja  (<18°C) → notificación HTTP
#   3. Presencia detectada + luz baja → sugerencia de encender luz
#   4. Humedad excesiva (>80%)     → notificación de ventilación
#
# El servicio receptor de notificaciones escucha en localhost:5000
# (ver notification_server.py)

ORION="http://localhost:1026"
NOTIF_URL="http://172.18.1.1:5000/notify"   # IP gateway Docker en Linux
# En Windows/Mac usar: http://host.docker.internal:5000/notify

echo "=============================================="
echo " Creando Suscripciones NGSI-v2 - Casa IoT"
echo "=============================================="

# -------------------------------------------------------
# 1. Alerta temperatura ALTA (>28°C) en cualquier sensor
# -------------------------------------------------------
echo ""
echo "[1/4] Suscripción: Temperatura alta..."
curl -s -o /dev/null -w "Temp alta → HTTP %{http_code}\n" -iX POST "$ORION/v2/subscriptions" \
  -H 'Content-Type: application/json' \
  -H 'fiware-service: smarthome' \
  -H 'fiware-servicepath: /' \
  -d "{
    \"description\": \"Alerta: temperatura > 28°C en cualquier habitación\",
    \"subject\": {
      \"entities\": [{ \"idPattern\": \"Sensor:.*\", \"type\": \"Sensor\" }],
      \"condition\": {
        \"attrs\": [\"temperature\"],
        \"expression\": { \"q\": \"temperature>28\" }
      }
    },
    \"notification\": {
      \"http\": { \"url\": \"$NOTIF_URL\" },
      \"attrs\": [\"temperature\", \"refRoom\"],
      \"attrsFormat\": \"keyValues\",
      \"metadata\": [\"dateModified\"]
    },
    \"throttling\": 300
  }"

# -------------------------------------------------------
# 2. Alerta temperatura BAJA (<18°C)
# -------------------------------------------------------
echo "[2/4] Suscripción: Temperatura baja..."
curl -s -o /dev/null -w "Temp baja → HTTP %{http_code}\n" -iX POST "$ORION/v2/subscriptions" \
  -H 'Content-Type: application/json' \
  -H 'fiware-service: smarthome' \
  -H 'fiware-servicepath: /' \
  -d "{
    \"description\": \"Alerta: temperatura < 18°C en cualquier habitación\",
    \"subject\": {
      \"entities\": [{ \"idPattern\": \"Sensor:.*\", \"type\": \"Sensor\" }],
      \"condition\": {
        \"attrs\": [\"temperature\"],
        \"expression\": { \"q\": \"temperature<18\" }
      }
    },
    \"notification\": {
      \"http\": { \"url\": \"$NOTIF_URL\" },
      \"attrs\": [\"temperature\", \"refRoom\"],
      \"attrsFormat\": \"keyValues\",
      \"metadata\": [\"dateModified\"]
    },
    \"throttling\": 300
  }"

# -------------------------------------------------------
# 3. Presencia detectada con poca luz (luminosidad < 30%)
# -------------------------------------------------------
echo "[3/4] Suscripción: Presencia + luz baja..."
curl -s -o /dev/null -w "Presencia → HTTP %{http_code}\n" -iX POST "$ORION/v2/subscriptions" \
  -H 'Content-Type: application/json' \
  -H 'fiware-service: smarthome' \
  -H 'fiware-servicepath: /' \
  -d "{
    \"description\": \"Presencia detectada con luminosidad baja (<30%)\",
    \"subject\": {
      \"entities\": [{ \"idPattern\": \"Sensor:.*\", \"type\": \"Sensor\" }],
      \"condition\": {
        \"attrs\": [\"presence\", \"luminosity\"],
        \"expression\": { \"q\": \"presence==1;luminosity<30\" }
      }
    },
    \"notification\": {
      \"http\": { \"url\": \"$NOTIF_URL\" },
      \"attrs\": [\"presence\", \"luminosity\", \"refRoom\"],
      \"attrsFormat\": \"keyValues\"
    },
    \"throttling\": 60
  }"

# -------------------------------------------------------
# 4. Humedad excesiva (>80%)
# -------------------------------------------------------
echo "[4/4] Suscripción: Humedad excesiva..."
curl -s -o /dev/null -w "Humedad → HTTP %{http_code}\n" -iX POST "$ORION/v2/subscriptions" \
  -H 'Content-Type: application/json' \
  -H 'fiware-service: smarthome' \
  -H 'fiware-servicepath: /' \
  -d "{
    \"description\": \"Alerta: humedad > 80% (riesgo de moho)\",
    \"subject\": {
      \"entities\": [{ \"idPattern\": \"Sensor:.*\", \"type\": \"Sensor\" }],
      \"condition\": {
        \"attrs\": [\"humidity\"],
        \"expression\": { \"q\": \"humidity>80\" }
      }
    },
    \"notification\": {
      \"http\": { \"url\": \"$NOTIF_URL\" },
      \"attrs\": [\"humidity\", \"refRoom\"],
      \"attrsFormat\": \"keyValues\",
      \"metadata\": [\"dateModified\"]
    },
    \"throttling\": 600
  }"

echo ""
echo "✅ Suscripciones creadas."
echo ""
echo "Suscripciones activas:"
curl -s "$ORION/v2/subscriptions" \
  -H 'fiware-service: smarthome' \
  -H 'fiware-servicepath: /' | python3 -c "
import sys, json
subs = json.load(sys.stdin)
for s in subs:
    print('  ID:', s['id'], '|', s.get('description',''))
" 2>/dev/null
