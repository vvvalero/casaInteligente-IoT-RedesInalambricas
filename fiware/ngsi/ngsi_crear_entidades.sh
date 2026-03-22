#!/bin/bash
# ngsi_crear_entidades.sh — Casa Inteligente IoT (3 nodos)
# Entidades: House, 3 Rooms, 3 Sensors, AccessLog base, Alerts base

ORION="http://localhost:1026"
CT='-H "Content-Type: application/json"'
FS='-H "fiware-service: smarthome" -H "fiware-servicepath: /"'

_post() {
  curl -s -o /dev/null -w "$1 → HTTP %{http_code}\n" -iX POST "$ORION/v2/entities" \
    -H 'Content-Type: application/json' \
    -H 'fiware-service: smarthome' \
    -H 'fiware-servicepath: /' \
    -d "$2"
}

echo "======================================"
echo " Creando entidades Casa Inteligente"
echo "======================================"

# ---- CASA ----
_post "House:001" '{
  "id":"urn:ngsi-ld:House:001","type":"House",
  "name":{"type":"Text","value":"Casa Inteligente IoT"},
  "address":{"type":"PostalAddress","value":{
    "streetAddress":"C/ Ejemplo, 1","addressLocality":"Albacete",
    "postalCode":"02001","addressCountry":"ES"}},
  "location":{"type":"geo:json","value":{"type":"Point","coordinates":[-1.8570,38.9909]}},
  "numRooms":{"type":"Integer","value":3}
}'

# ---- HABITACIONES ----
for data in \
  '{"id":"urn:ngsi-ld:Room:salon","type":"Room","name":{"type":"Text","value":"Salon"},"floor":{"type":"Integer","value":1},"area":{"type":"Number","value":35},"refHouse":{"type":"Relationship","value":"urn:ngsi-ld:House:001"}}' \
  '{"id":"urn:ngsi-ld:Room:dormitorio","type":"Room","name":{"type":"Text","value":"Dormitorio"},"floor":{"type":"Integer","value":2},"area":{"type":"Number","value":20},"refHouse":{"type":"Relationship","value":"urn:ngsi-ld:House:001"}}' \
  '{"id":"urn:ngsi-ld:Room:exterior","type":"Room","name":{"type":"Text","value":"Exterior"},"floor":{"type":"Integer","value":0},"area":{"type":"Number","value":50},"refHouse":{"type":"Relationship","value":"urn:ngsi-ld:House:001"}}'; do
  id=$(echo $data | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")
  _post "$id" "$data"
done

# ---- SENSORES ----
# Sensor:s1 — Salón (temp, hum, lux, presión, acelerómetro)
_post "Sensor:s1" '{
  "id":"Sensor:s1","type":"Sensor",
  "name":{"type":"Text","value":"Nodo Salon"},
  "refRoom":{"type":"Relationship","value":"urn:ngsi-ld:Room:salon"},
  "nodeType":{"type":"Text","value":"salon"}
}'

# Sensor:s2 — Dormitorio (temp, hum, lux, NFC)
_post "Sensor:s2" '{
  "id":"Sensor:s2","type":"Sensor",
  "name":{"type":"Text","value":"Nodo Dormitorio"},
  "refRoom":{"type":"Relationship","value":"urn:ngsi-ld:Room:dormitorio"},
  "nodeType":{"type":"Text","value":"dormitorio"},
  "nfcAuthorizedUIDs":{"type":"Text","value":"A1B2C3D4,DEADBEEF"}
}'

# Sensor:s3 — Exterior (temp, hum, presión, BLE)
_post "Sensor:s3" '{
  "id":"Sensor:s3","type":"Sensor",
  "name":{"type":"Text","value":"Nodo Exterior"},
  "refRoom":{"type":"Relationship","value":"urn:ngsi-ld:Room:exterior"},
  "nodeType":{"type":"Text","value":"exterior"},
  "aforoMaximo":{"type":"Integer","value":5}
}'

# ---- ALERTAS INICIALES (vacías, se actualizarán dinámicamente) ----
for tipo in temp_high temp_low humidity vibration aforo nfc_denied pressure_low; do
  _post "Alert:$tipo" "{
    \"id\":\"Alert:$tipo\",\"type\":\"Alert\",
    \"alertType\":{\"type\":\"Text\",\"value\":\"$tipo\"},
    \"active\":{\"type\":\"Boolean\",\"value\":false},
    \"message\":{\"type\":\"Text\",\"value\":\"\"},
    \"severity\":{\"type\":\"Text\",\"value\":\"info\"},
    \"refSensor\":{\"type\":\"Relationship\",\"value\":\"\"},
    \"timestamp\":{\"type\":\"DateTime\",\"value\":\"1970-01-01T00:00:00Z\"}
  }"
done

echo ""
echo "Verificando entidades creadas:"
curl -s "$ORION/v2/entities?options=keyValues&type=Sensor,Room,House,Alert" \
  -H 'fiware-service: smarthome' -H 'fiware-servicepath: /' | python3 -m json.tool 2>/dev/null || echo "(instala python3 para formato legible)"
