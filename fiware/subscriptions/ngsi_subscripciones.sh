#!/bin/bash
# ngsi_subscripciones.sh — Suscripciones NGSI-v2
# Casa Inteligente IoT · 3x LoPy4 + Pysense
#
# Las suscripciones con filtro numérico (q=temperature>28) fallan
# si el atributo aún no existe en la entidad (antes del primer uplink).
# Solución: se crean SIN expression. El filtrado lo hace notification_server.py.

ORION="http://localhost:1026"
NOTIF="http://notification-server:5000/notify"

_sub() {
  label=$1; body=$2
  curl -s -o /dev/null -w "$label -> HTTP %{http_code}\n" -X POST "$ORION/v2/subscriptions" \
    -H 'Content-Type: application/json' \
    -H 'fiware-service: smarthome' \
    -H 'fiware-servicepath: /' \
    -d "$body"
}

echo "Creando suscripciones..."

_sub "[1] Temperatura" \
  '{"description":"Cambio de temperatura en cualquier nodo","subject":{"entities":[{"idPattern":"Sensor:.*","type":"Sensor"}],"condition":{"attrs":["temperature"]}},"notification":{"http":{"url":"'"$NOTIF"'"},"attrs":["temperature","humidity","luminosity","vibrationDetected","accelerationMagnitude","refRoom","nodeType"],"attrsFormat":"keyValues"},"throttling":60}'

_sub "[2] Humedad" \
  '{"description":"Cambio de humedad en cualquier nodo","subject":{"entities":[{"idPattern":"Sensor:.*","type":"Sensor"}],"condition":{"attrs":["humidity"]}},"notification":{"http":{"url":"'"$NOTIF"'"},"attrs":["temperature","humidity","luminosity","refRoom","nodeType"],"attrsFormat":"keyValues"},"throttling":60}'

_sub "[3] Vibracion" \
  '{"description":"Vibracion detectada acelerometro","subject":{"entities":[{"id":"Sensor:s1","type":"Sensor"}],"condition":{"attrs":["vibrationDetected"]}},"notification":{"http":{"url":"'"$NOTIF"'"},"attrs":["vibrationDetected","accelerationMagnitude","refRoom"],"attrsFormat":"keyValues"},"throttling":30}'

_sub "[4] NFC detectado" \
  '{"description":"Tarjeta NFC detectada en dormitorio","subject":{"entities":[{"id":"Sensor:s2","type":"Sensor"}],"condition":{"attrs":["nfcDetected"]}},"notification":{"http":{"url":"'"$NOTIF"'"},"attrs":["nfcDetected","nfcUidPartial","nfcAuthorizedUIDs"],"attrsFormat":"keyValues"},"throttling":5}'

_sub "[5] BLE exterior" \
  '{"description":"Cambio en dispositivos BLE cercanos","subject":{"entities":[{"id":"Sensor:s3","type":"Sensor"}],"condition":{"attrs":["bleDevicesNearby"]}},"notification":{"http":{"url":"'"$NOTIF"'"},"attrs":["bleDevicesNearby","aforoMaximo","refRoom"],"attrsFormat":"keyValues"},"throttling":60}'

_sub "[6] Luminosidad exterior" \
  '{"description":"Cambio de luminosidad en exterior","subject":{"entities":[{"id":"Sensor:s3","type":"Sensor"}],"condition":{"attrs":["luminosity"]}},"notification":{"http":{"url":"'"$NOTIF"'"},"attrs":["luminosity","refRoom"],"attrsFormat":"keyValues"},"throttling":300}'

_sub "[7] Acceso NFC" \
  '{"description":"Acceso NFC registrado (autorizado o denegado)","subject":{"entities":[{"idPattern":"AccessLog:.*","type":"AccessLog"}],"condition":{"attrs":["authorized"]}},"notification":{"http":{"url":"'"$NOTIF"'"},"attrs":["nfcUID","authorized","timestamp"],"attrsFormat":"keyValues"},"throttling":5}'

echo ""
echo "Suscripciones activas:"
curl -s "$ORION/v2/subscriptions" \
  -H 'fiware-service: smarthome' \
  -H 'fiware-servicepath: /' \
  | python3 -c "
import sys, json
subs = json.load(sys.stdin)
print('  Total:', len(subs))
for s in subs:
    print('  ', s['id'], '|', s.get('description',''))
" 2>/dev/null
