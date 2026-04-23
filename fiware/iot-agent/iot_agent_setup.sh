#!/bin/bash
# iot_agent_setup.sh — Registra servicios y dispositivos en el IoT Agent
# Casa Inteligente IoT · 3x LoPy4 + Pysense
#
# Registra únicamente los 3 nodos reales del proyecto:
#   s1 → Nodo salón      (temp, hum, lux, presión, acelerómetro)
#   s2 → Nodo dormitorio (temp, hum, lux, NFC)
#   s3 → Nodo exterior   (temp, hum, presión, BLE)
#
# Prerequisito: ngsi_crear_entidades.sh ya ejecutado

IOT_AGENT="http://localhost:4041"
ORION="http://orion:1026"

echo "=================================================="
echo " Configurando IoT Agent - Casa Inteligente IoT"
echo "=================================================="

# -------------------------------------------------------
# Servicio de sensores
# Define los atributos que el IoT Agent mapeará a Orion
# cuando lleguen datos por MQTT desde TTN
# -------------------------------------------------------
echo ""
echo "--- [A] Servicio de Sensores ---"
curl -s -o /dev/null -w "Servicio Sensor → HTTP %{http_code}\n" -X POST "$IOT_AGENT/iot/services" \
  -H 'Content-Type: application/json' \
  -H 'fiware-service: smarthome' \
  -H 'fiware-servicepath: /' \
  -d "{
    \"services\": [{
      \"apikey\":      \"smarthome-sensor-key\",
      \"cbroker\":     \"$ORION\",
      \"entity_type\": \"Sensor\",
      \"resource\":    \"\",
      \"protocol\":    \"PDI-IoTA-UltraLight\",
      \"transport\":   \"MQTT\",
      \"timezone\":    \"Europe/Madrid\",
      \"attributes\": [
        { \"object_id\": \"temperature\",           \"name\": \"temperature\",           \"type\": \"Number\" },
        { \"object_id\": \"humidity\",              \"name\": \"humidity\",              \"type\": \"Number\" },
        { \"object_id\": \"luminosity\",            \"name\": \"luminosity\",            \"type\": \"Number\" },
        { \"object_id\": \"barometricPressure\",    \"name\": \"barometricPressure\",    \"type\": \"Number\" },
        { \"object_id\": \"vibrationDetected\",     \"name\": \"vibrationDetected\",     \"type\": \"Boolean\" },
        { \"object_id\": \"accelerationMagnitude\", \"name\": \"accelerationMagnitude\", \"type\": \"Number\" },
        { \"object_id\": \"nfcDetected\",           \"name\": \"nfcDetected\",           \"type\": \"Boolean\" },
        { \"object_id\": \"nfcUidPartial\",         \"name\": \"nfcUidPartial\",         \"type\": \"Number\" },
        { \"object_id\": \"bleDevicesNearby\",      \"name\": \"bleDevicesNearby\",      \"type\": \"Number\" },
        { \"object_id\": \"room\",                  \"name\": \"room\",                  \"type\": \"Text\" },
        { \"object_id\": \"roomId\",                \"name\": \"roomId\",                \"type\": \"Number\" }
      ]
    }]
  }"

# -------------------------------------------------------
# Registrar los 3 dispositivos (uno por nodo)
# -------------------------------------------------------
echo ""
echo "--- [B] Registrando 3 nodos ---"

curl -s -o /dev/null -w "Nodo salon (s1)      → HTTP %{http_code}\n" -X POST "$IOT_AGENT/iot/devices" \
  -H 'Content-Type: application/json' \
  -H 'fiware-service: smarthome' \
  -H 'fiware-servicepath: /' \
  -d '{
    "devices": [{
      "device_id":   "s1",
      "entity_name": "Sensor:s1",
      "entity_type": "Sensor"
    }]
  }'

curl -s -o /dev/null -w "Nodo dormitorio (s2) → HTTP %{http_code}\n" -X POST "$IOT_AGENT/iot/devices" \
  -H 'Content-Type: application/json' \
  -H 'fiware-service: smarthome' \
  -H 'fiware-servicepath: /' \
  -d '{
    "devices": [{
      "device_id":   "s2",
      "entity_name": "Sensor:s2",
      "entity_type": "Sensor"
    }]
  }'

curl -s -o /dev/null -w "Nodo exterior (s3)   → HTTP %{http_code}\n" -X POST "$IOT_AGENT/iot/devices" \
  -H 'Content-Type: application/json' \
  -H 'fiware-service: smarthome' \
  -H 'fiware-servicepath: /' \
  -d '{
    "devices": [{
      "device_id":   "s3",
      "entity_name": "Sensor:s3",
      "entity_type": "Sensor"
    }]
  }'

echo ""
echo "✅ IoT Agent configurado."
echo ""
echo "Verificando dispositivos registrados:"
curl -s "$IOT_AGENT/iot/devices" \
  -H 'fiware-service: smarthome' \
  -H 'fiware-servicepath: /' \
  | python3 -c "
import sys, json
data = json.load(sys.stdin)
print('  Total dispositivos:', data.get('count', 0))
for d in data.get('devices', []):
    print('  ', d['device_id'], '→', d['entity_name'])
" 2>/dev/null
