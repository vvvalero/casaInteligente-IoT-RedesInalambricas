#!/bin/bash
# iot_agent_setup.sh
# Registra servicios y dispositivos en el IoT Agent UltraLight 2.0 con MQTT
#
# Orden de ejecución:
#   1. Crear servicio de sensores
#   2. Registrar los 5 sensores
#   3. Crear servicio de actuadores (lámparas)
#   4. Registrar las 5 lámparas
#   5. Crear servicio de actuadores (AC)
#   6. Registrar los 5 AC
#   7. Crear servicio de alarma
#   8. Registrar la alarma
#
# Prerequisito: entidades NGSI-v2 ya creadas (ngsi_crear_entidades.sh)

IOT_AGENT="http://localhost:4041"
ORION="http://orion:1026"   # URL interna Docker
FS_SENSOR='-H "fiware-service: smarthome" -H "fiware-servicepath: /"'

echo "=================================================="
echo " Configurando IoT Agent - Casa Inteligente IoT"
echo "=================================================="

# ===========================================================
# SENSORES
# ===========================================================

echo ""
echo "--- [A] Servicio de Sensores ---"
curl -s -o /dev/null -w "Servicio Sensor → HTTP %{http_code}\n" -iX POST "$IOT_AGENT/iot/services" \
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
        {
          \"object_id\": \"t\", \"name\": \"temperature\", \"type\": \"Number\",
          \"metadata\": { \"unitCode\": { \"type\": \"Text\", \"value\": \"CEL\" } }
        },
        {
          \"object_id\": \"h\", \"name\": \"humidity\", \"type\": \"Number\",
          \"metadata\": { \"unitCode\": { \"type\": \"Text\", \"value\": \"P1\" } }
        },
        {
          \"object_id\": \"l\", \"name\": \"luminosity\", \"type\": \"Number\",
          \"metadata\": { \"unitCode\": { \"type\": \"Text\", \"value\": \"P1\" } }
        },
        {
          \"object_id\": \"p\", \"name\": \"presence\", \"type\": \"Integer\"
        }
      ]
    }]
  }"

echo ""
echo "--- [B] Registrando 5 Sensores ---"
for i in 1 2 3 4 5; do
  curl -s -o /dev/null -w "Sensor s$i → HTTP %{http_code}\n" -iX POST "$IOT_AGENT/iot/devices" \
    -H 'Content-Type: application/json' \
    -H 'fiware-service: smarthome' \
    -H 'fiware-servicepath: /' \
    -d "{
      \"devices\": [{
        \"device_id\":   \"s$i\",
        \"entity_type\": \"Sensor\"
      }]
    }"
done

# ===========================================================
# LÁMPARAS (actuadores)
# ===========================================================

echo ""
echo "--- [C] Servicio de Lámparas ---"
curl -s -o /dev/null -w "Servicio Lamp → HTTP %{http_code}\n" -iX POST "$IOT_AGENT/iot/services" \
  -H 'Content-Type: application/json' \
  -H 'fiware-service: smarthome' \
  -H 'fiware-servicepath: /' \
  -d "{
    \"services\": [{
      \"apikey\":      \"smarthome-lamp-key\",
      \"cbroker\":     \"$ORION\",
      \"entity_type\": \"Lamp\",
      \"resource\":    \"\",
      \"protocol\":    \"PDI-IoTA-UltraLight\",
      \"transport\":   \"MQTT\",
      \"timezone\":    \"Europe/Madrid\",
      \"commands\": [
        { \"name\": \"onOff\",     \"type\": \"command\" },
        { \"name\": \"nivelLuz\",  \"type\": \"command\" }
      ]
    }]
  }"

echo ""
echo "--- [D] Registrando 5 Lámparas ---"
for i in 1 2 3 4 5; do
  curl -s -o /dev/null -w "Lamp lamp$i → HTTP %{http_code}\n" -iX POST "$IOT_AGENT/iot/devices" \
    -H 'Content-Type: application/json' \
    -H 'fiware-service: smarthome' \
    -H 'fiware-servicepath: /' \
    -d "{
      \"devices\": [{
        \"device_id\":   \"lamp$i\",
        \"entity_type\": \"Lamp\"
      }]
    }"
done

# ===========================================================
# AIRES ACONDICIONADOS (actuadores)
# ===========================================================

echo ""
echo "--- [E] Servicio de AC ---"
curl -s -o /dev/null -w "Servicio AC → HTTP %{http_code}\n" -iX POST "$IOT_AGENT/iot/services" \
  -H 'Content-Type: application/json' \
  -H 'fiware-service: smarthome' \
  -H 'fiware-servicepath: /' \
  -d "{
    \"services\": [{
      \"apikey\":      \"smarthome-ac-key\",
      \"cbroker\":     \"$ORION\",
      \"entity_type\": \"AC\",
      \"resource\":    \"\",
      \"protocol\":    \"PDI-IoTA-UltraLight\",
      \"transport\":   \"MQTT\",
      \"timezone\":    \"Europe/Madrid\",
      \"commands\": [
        { \"name\": \"onOff\",    \"type\": \"command\" },
        { \"name\": \"heatCool\", \"type\": \"command\" }
      ]
    }]
  }"

echo ""
echo "--- [F] Registrando 5 AC ---"
for i in 1 2 3 4 5; do
  curl -s -o /dev/null -w "AC ac$i → HTTP %{http_code}\n" -iX POST "$IOT_AGENT/iot/devices" \
    -H 'Content-Type: application/json' \
    -H 'fiware-service: smarthome' \
    -H 'fiware-servicepath: /' \
    -d "{
      \"devices\": [{
        \"device_id\":   \"ac$i\",
        \"entity_type\": \"AC\"
      }]
    }"
done

# ===========================================================
# ALARMA (actuador)
# ===========================================================

echo ""
echo "--- [G] Servicio de Alarma ---"
curl -s -o /dev/null -w "Servicio Alarm → HTTP %{http_code}\n" -iX POST "$IOT_AGENT/iot/services" \
  -H 'Content-Type: application/json' \
  -H 'fiware-service: smarthome' \
  -H 'fiware-servicepath: /' \
  -d "{
    \"services\": [{
      \"apikey\":      \"smarthome-alarm-key\",
      \"cbroker\":     \"$ORION\",
      \"entity_type\": \"Alarm\",
      \"resource\":    \"\",
      \"protocol\":    \"PDI-IoTA-UltraLight\",
      \"transport\":   \"MQTT\",
      \"timezone\":    \"Europe/Madrid\",
      \"commands\": [
        { \"name\": \"activar\",  \"type\": \"command\" },
        { \"name\": \"silenciar\",\"type\": \"command\" }
      ]
    }]
  }"

echo ""
echo "--- [H] Registrando Alarma ---"
curl -s -o /dev/null -w "Alarm alarm001 → HTTP %{http_code}\n" -iX POST "$IOT_AGENT/iot/devices" \
  -H 'Content-Type: application/json' \
  -H 'fiware-service: smarthome' \
  -H 'fiware-servicepath: /' \
  -d '{
    "devices": [{
      "device_id":   "alarm001",
      "entity_type": "Alarm"
    }]
  }'

echo ""
echo "✅ IoT Agent configurado."
echo ""
echo "Verificando dispositivos registrados:"
curl -s "$IOT_AGENT/iot/devices" \
  -H 'fiware-service: smarthome' \
  -H 'fiware-servicepath: /' | python3 -m json.tool 2>/dev/null || \
curl -s "$IOT_AGENT/iot/devices" \
  -H 'fiware-service: smarthome' \
  -H 'fiware-servicepath: /'
