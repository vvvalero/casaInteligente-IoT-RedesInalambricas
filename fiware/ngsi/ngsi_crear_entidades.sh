#!/bin/bash
# ngsi_crear_entidades.sh
# Crea todas las entidades NGSI-v2 de la casa inteligente en Orion Context Broker
#
# Entidades:
#   - 1 entidad House (la casa)
#   - 5 entidades Room (salón, cocina, dormitorio, baño, exterior)
#   - 5 entidades Sensor (uno por habitación)
#   - 5 entidades Lamp   (lámpara por habitación)
#   - 5 entidades AC     (aire acondicionado por habitación)
#   - 1 entidad Alarm    (alarma general de la casa)
#
# Uso: bash ngsi_crear_entidades.sh

ORION="http://localhost:1026"
HEADERS='-H "Content-Type: application/json" -H "fiware-service: smarthome" -H "fiware-servicepath: /"'
FS='-H "fiware-service: smarthome" -H "fiware-servicepath: /"'

echo "=============================================="
echo " Creando entidades Casa Inteligente NGSI-v2"
echo "=============================================="

# -------------------------------------------------------
# 1. CASA
# -------------------------------------------------------
echo "[1/4] Creando entidad House..."
curl -s -o /dev/null -w "House → HTTP %{http_code}\n" -iX POST "$ORION/v2/entities" \
  -H 'Content-Type: application/json' \
  -H 'fiware-service: smarthome' \
  -H 'fiware-servicepath: /' \
  -d '{
    "id":   "urn:ngsi-ld:House:001",
    "type": "House",
    "name": { "type": "Text",          "value": "Casa Inteligente IoT" },
    "address": {
      "type": "PostalAddress",
      "value": {
        "streetAddress":    "C/ Ejemplo, 1",
        "addressLocality":  "Albacete",
        "postalCode":       "02001",
        "addressCountry":   "ES"
      }
    },
    "location": {
      "type": "geo:json",
      "value": { "type": "Point", "coordinates": [-1.8570, 38.9909] }
    },
    "numRooms": { "type": "Integer", "value": 5 }
  }'

# -------------------------------------------------------
# 2. HABITACIONES (5)
# -------------------------------------------------------
echo "[2/4] Creando habitaciones..."

declare -A ROOMS
ROOMS["salon"]="Salón"
ROOMS["cocina"]="Cocina"
ROOMS["dormitorio"]="Dormitorio Principal"
ROOMS["bano"]="Baño"
ROOMS["exterior"]="Exterior / Jardín"

declare -A ROOM_AREA
ROOM_AREA["salon"]=35
ROOM_AREA["cocina"]=15
ROOM_AREA["dormitorio"]=20
ROOM_AREA["bano"]=8
ROOM_AREA["exterior"]=50

declare -A ROOM_FLOOR
ROOM_FLOOR["salon"]=1
ROOM_FLOOR["cocina"]=1
ROOM_FLOOR["dormitorio"]=2
ROOM_FLOOR["bano"]=2
ROOM_FLOOR["exterior"]=0

for room_id in salon cocina dormitorio bano exterior; do
  curl -s -o /dev/null -w "Room:$room_id → HTTP %{http_code}\n" -iX POST "$ORION/v2/entities" \
    -H 'Content-Type: application/json' \
    -H 'fiware-service: smarthome' \
    -H 'fiware-servicepath: /' \
    -d "{
      \"id\":   \"urn:ngsi-ld:Room:$room_id\",
      \"type\": \"Room\",
      \"name\":  { \"type\": \"Text\",    \"value\": \"${ROOMS[$room_id]}\" },
      \"floor\": { \"type\": \"Integer\", \"value\": ${ROOM_FLOOR[$room_id]} },
      \"area\":  {
        \"type\": \"Number\", \"value\": ${ROOM_AREA[$room_id]},
        \"metadata\": { \"unitCode\": { \"type\": \"Text\", \"value\": \"M2\" } }
      },
      \"refHouse\": { \"type\": \"Relationship\", \"value\": \"urn:ngsi-ld:House:001\" }
    }"
done

# -------------------------------------------------------
# 3. SENSORES (1 por habitación)
#    Atributos activos (temperatura, humedad, luminosidad, presencia)
#    se inicializan en null — serán rellenados por el IoT Agent
# -------------------------------------------------------
echo "[3/4] Creando sensores..."

SENSOR_NUM=1
for room_id in salon cocina dormitorio bano exterior; do
  SENSOR_ID="s$SENSOR_NUM"
  curl -s -o /dev/null -w "Sensor:$SENSOR_ID → HTTP %{http_code}\n" -iX POST "$ORION/v2/entities" \
    -H 'Content-Type: application/json' \
    -H 'fiware-service: smarthome' \
    -H 'fiware-servicepath: /' \
    -d "{
      \"id\":   \"Sensor:$SENSOR_ID\",
      \"type\": \"Sensor\",
      \"name\": { \"type\": \"Text\", \"value\": \"urn:ngsi-ld:Sensor:$SENSOR_ID\" },
      \"refRoom\": { \"type\": \"Relationship\", \"value\": \"urn:ngsi-ld:Room:$room_id\" }
    }"
  SENSOR_NUM=$((SENSOR_NUM + 1))
done

# -------------------------------------------------------
# 4. ACTUADORES
#    4a. Lámparas (1 por habitación)
#    4b. Aires acondicionados (1 por habitación)
#    4c. Alarma (1 general de la casa)
# -------------------------------------------------------
echo "[4/4] Creando actuadores..."

AC_NUM=1
LAMP_NUM=1
for room_id in salon cocina dormitorio bano exterior; do
  # Lámpara
  curl -s -o /dev/null -w "Lamp:lamp$LAMP_NUM → HTTP %{http_code}\n" -iX POST "$ORION/v2/entities" \
    -H 'Content-Type: application/json' \
    -H 'fiware-service: smarthome' \
    -H 'fiware-servicepath: /' \
    -d "{
      \"id\":   \"Lamp:lamp$LAMP_NUM\",
      \"type\": \"Lamp\",
      \"name\": { \"type\": \"Text\", \"value\": \"urn:ngsi-ld:Lamp:lamp$LAMP_NUM\" },
      \"refRoom\": { \"type\": \"Relationship\", \"value\": \"urn:ngsi-ld:Room:$room_id\" }
    }"

  # Aire Acondicionado
  curl -s -o /dev/null -w "AC:ac$AC_NUM → HTTP %{http_code}\n" -iX POST "$ORION/v2/entities" \
    -H 'Content-Type: application/json' \
    -H 'fiware-service: smarthome' \
    -H 'fiware-servicepath: /' \
    -d "{
      \"id\":   \"AC:ac$AC_NUM\",
      \"type\": \"AC\",
      \"name\": { \"type\": \"Text\", \"value\": \"urn:ngsi-ld:AC:ac$AC_NUM\" },
      \"refRoom\": { \"type\": \"Relationship\", \"value\": \"urn:ngsi-ld:Room:$room_id\" }
    }"

  LAMP_NUM=$((LAMP_NUM + 1))
  AC_NUM=$((AC_NUM + 1))
done

# Alarma general
curl -s -o /dev/null -w "Alarm:alarm001 → HTTP %{http_code}\n" -iX POST "$ORION/v2/entities" \
  -H 'Content-Type: application/json' \
  -H 'fiware-service: smarthome' \
  -H 'fiware-servicepath: /' \
  -d '{
    "id":   "Alarm:alarm001",
    "type": "Alarm",
    "name": { "type": "Text", "value": "urn:ngsi-ld:Alarm:alarm001" },
    "refHouse": { "type": "Relationship", "value": "urn:ngsi-ld:House:001" }
  }'

echo ""
echo "✅ Entidades creadas. Verificando con GET /v2/entities..."
curl -s "$ORION/v2/entities?options=keyValues" \
  -H 'fiware-service: smarthome' \
  -H 'fiware-servicepath: /' | python3 -m json.tool 2>/dev/null || \
curl -s "$ORION/v2/entities?options=keyValues" \
  -H 'fiware-service: smarthome' \
  -H 'fiware-servicepath: /'
