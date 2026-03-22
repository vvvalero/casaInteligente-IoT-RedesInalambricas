#!/bin/bash
# ngsi_subscripciones.sh — 10 suscripciones NGSI-v2
# Casa Inteligente IoT · 3x LoPy4 + Pysense

ORION="http://localhost:1026"
NOTIF="http://172.18.1.1:5000/notify"
# Windows/Mac: NOTIF="http://host.docker.internal:5000/notify"

_sub() {
  label=$1; body=$2
  curl -s -o /dev/null -w "$label → HTTP %{http_code}\n" -iX POST "$ORION/v2/subscriptions" \
    -H 'Content-Type: application/json' \
    -H 'fiware-service: smarthome' \
    -H 'fiware-servicepath: /' \
    -d "$body"
}

echo "Creando suscripciones..."

# 1. Temperatura alta (>28°C) — todos los nodos
_sub "[1] Temp alta" "{
  \"description\":\"Temperatura alta > 28C\",
  \"subject\":{\"entities\":[{\"idPattern\":\"Sensor:.*\",\"type\":\"Sensor\"}],
    \"condition\":{\"attrs\":[\"temperature\"],\"expression\":{\"q\":\"temperature>28\"}}},
  \"notification\":{\"http\":{\"url\":\"$NOTIF\"},\"attrs\":[\"temperature\",\"refRoom\",\"nodeType\"],\"attrsFormat\":\"keyValues\"},
  \"throttling\":300}"

# 2. Temperatura baja (<10°C) — todos los nodos
_sub "[2] Temp baja" "{
  \"description\":\"Temperatura baja < 10C\",
  \"subject\":{\"entities\":[{\"idPattern\":\"Sensor:.*\",\"type\":\"Sensor\"}],
    \"condition\":{\"attrs\":[\"temperature\"],\"expression\":{\"q\":\"temperature<10\"}}},
  \"notification\":{\"http\":{\"url\":\"$NOTIF\"},\"attrs\":[\"temperature\",\"refRoom\",\"nodeType\"],\"attrsFormat\":\"keyValues\"},
  \"throttling\":300}"

# 3. Humedad alta (>80%) — todos los nodos
_sub "[3] Humedad alta" "{
  \"description\":\"Humedad > 80%\",
  \"subject\":{\"entities\":[{\"idPattern\":\"Sensor:.*\",\"type\":\"Sensor\"}],
    \"condition\":{\"attrs\":[\"humidity\"],\"expression\":{\"q\":\"humidity>80\"}}},
  \"notification\":{\"http\":{\"url\":\"$NOTIF\"},\"attrs\":[\"humidity\",\"refRoom\",\"nodeType\"],\"attrsFormat\":\"keyValues\"},
  \"throttling\":600}"

# 4. Vibración detectada (acelerómetro) — nodo salón
_sub "[4] Vibracion" "{
  \"description\":\"Vibracion detectada acelerometro\",
  \"subject\":{\"entities\":[{\"id\":\"Sensor:s1\",\"type\":\"Sensor\"}],
    \"condition\":{\"attrs\":[\"vibrationDetected\"],\"expression\":{\"q\":\"vibrationDetected==true\"}}},
  \"notification\":{\"http\":{\"url\":\"$NOTIF\"},\"attrs\":[\"vibrationDetected\",\"accelerationMagnitude\",\"refRoom\"],\"attrsFormat\":\"keyValues\"},
  \"throttling\":30}"

# 5. NFC detectado — nodo dormitorio
_sub "[5] NFC detectado" "{
  \"description\":\"Tarjeta NFC detectada en dormitorio\",
  \"subject\":{\"entities\":[{\"id\":\"Sensor:s2\",\"type\":\"Sensor\"}],
    \"condition\":{\"attrs\":[\"nfcDetected\"]}},
  \"notification\":{\"http\":{\"url\":\"$NOTIF\"},\"attrs\":[\"nfcDetected\",\"nfcUidPartial\",\"nfcAuthorizedUIDs\"],\"attrsFormat\":\"keyValues\"},
  \"throttling\":5}"

# 6. Aforo BLE alto (>5 dispositivos) — nodo exterior
_sub "[6] Aforo BLE" "{
  \"description\":\"Aforo BLE superado (>5 dispositivos)\",
  \"subject\":{\"entities\":[{\"id\":\"Sensor:s3\",\"type\":\"Sensor\"}],
    \"condition\":{\"attrs\":[\"bleDevicesNearby\"],\"expression\":{\"q\":\"bleDevicesNearby>5\"}}},
  \"notification\":{\"http\":{\"url\":\"$NOTIF\"},\"attrs\":[\"bleDevicesNearby\",\"aforoMaximo\",\"refRoom\"],\"attrsFormat\":\"keyValues\"},
  \"throttling\":120}"

# 7. Luminosidad baja exterior (luminosity<50) — nodo exterior
_sub "[7] Lux exterior baja" "{
  \"description\":\"Luminosidad baja en exterior\",
  \"subject\":{\"entities\":[{\"id\":\"Sensor:s3\",\"type\":\"Sensor\"}],
    \"condition\":{\"attrs\":[\"luminosity\"],\"expression\":{\"q\":\"luminosity<50\"}}},
  \"notification\":{\"http\":{\"url\":\"$NOTIF\"},\"attrs\":[\"luminosity\",\"refRoom\"],\"attrsFormat\":\"keyValues\"},
  \"throttling\":300}"

# 8. Presión baja exterior (<1000 hPa) — nodo exterior
_sub "[8] Presion baja" "{
  \"description\":\"Presion atmosferica baja < 1000 hPa\",
  \"subject\":{\"entities\":[{\"id\":\"Sensor:s3\",\"type\":\"Sensor\"}],
    \"condition\":{\"attrs\":[\"barometricPressure\"],\"expression\":{\"q\":\"barometricPressure<1000\"}}},
  \"notification\":{\"http\":{\"url\":\"$NOTIF\"},\"attrs\":[\"barometricPressure\",\"temperature\",\"refRoom\"],\"attrsFormat\":\"keyValues\"},
  \"throttling\":600}"

# 9. Nueva entrada en AccessLog (NFC autorizado)
_sub "[9] Acceso NFC OK" "{
  \"description\":\"Acceso NFC autorizado registrado\",
  \"subject\":{\"entities\":[{\"idPattern\":\"AccessLog:.*\",\"type\":\"AccessLog\"}],
    \"condition\":{\"attrs\":[\"authorized\"],\"expression\":{\"q\":\"authorized==true\"}}},
  \"notification\":{\"http\":{\"url\":\"$NOTIF\"},\"attrs\":[\"nfcUID\",\"authorized\",\"timestamp\"],\"attrsFormat\":\"keyValues\"},
  \"throttling\":5}"

# 10. Nueva entrada en AccessLog (NFC denegado)
_sub "[10] Acceso NFC denegado" "{
  \"description\":\"Acceso NFC denegado registrado\",
  \"subject\":{\"entities\":[{\"idPattern\":\"AccessLog:.*\",\"type\":\"AccessLog\"}],
    \"condition\":{\"attrs\":[\"authorized\"],\"expression\":{\"q\":\"authorized==false\"}}},
  \"notification\":{\"http\":{\"url\":\"$NOTIF\"},\"attrs\":[\"nfcUID\",\"authorized\",\"timestamp\"],\"attrsFormat\":\"keyValues\"},
  \"throttling\":5}"

echo ""
echo "Suscripciones activas:"
curl -s "$ORION/v2/subscriptions" -H 'fiware-service: smarthome' -H 'fiware-servicepath: /' \
  | python3 -c "import sys,json; [print('  ',s['id'],'|',s.get('description','')) for s in json.load(sys.stdin)]" 2>/dev/null
