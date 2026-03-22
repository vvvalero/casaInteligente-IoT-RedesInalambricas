# Casa Inteligente IoT — Proyecto Final
## Dispositivos y Redes Inalámbricos · LoRaWAN + Fiware + NGSI-v2

---

## Arquitectura del sistema

```
┌──────────────────────────────────────────────────────────────────┐
│                  3× LoPy4 + Pysense + LEDs en protoboard         │
│                                                                  │
│  Nodo 1 — Salón          Nodo 2 — Dormitorio   Nodo 3 — Exterior │
│  SI7006A20 (T+H)         SI7006A20 (T+H)       SI7006A20 (T+H)  │
│  LTR329ALS01 (lux)       LTR329ALS01 (lux)     MPL3115A2 (pres) │
│  MPL3115A2 (presión)     PN532 NFC              BLE scanner      │
│  LIS2HH12 (aceleróm.)    LED externo RGB        LED externo RGB  │
│  LED externo RGB                                                  │
└─────────────────────────────┬────────────────────────────────────┘
                              │ LoRaWAN OTAA EU868 · Cayenne LPP
                              ▼
                 ┌────────────────────────┐
                 │   The Things Network   │
                 │   ttn_payload_         │
                 │   formatter.js         │
                 │   decodeUplink /       │
                 │   encodeDownlink       │
                 └────────────┬───────────┘
                              │ HTTP Webhook (JSON)
                 ┌────────────▼───────────────────────────┐
                 │         FIWARE STACK (Docker)           │
                 │                                        │
                 │  IoT Agent → Orion Context Broker      │
                 │                    │                   │
                 │  Sensor:s1/s2/s3   MongoDB             │
                 │  Room:salon/dorm/ext                   │
                 │  Alert:temp_high/low/...               │
                 │  AccessLog:N (historial NFC)           │
                 └────────────┬───────────────────────────┘
                              │ Suscripciones NGSI-v2 (10 reglas)
                              ▼
                 ┌────────────────────────┐
                 │  notification_server   │     TTN API
                 │                        │ ──────────────►  Downlink
                 │  10 automatizaciones   │                  al LoPy4
                 │  · Crea AlertLog       │
                 │  · Crea AccessLog NFC  │
                 │  · Downlink automático │
                 └────────────────────────┘
```

---

## Hardware por nodo

| Componente | Nodo 1 Salón | Nodo 2 Dormitorio | Nodo 3 Exterior |
|---|:---:|:---:|:---:|
| LoPy4 + Pysense | ✓ | ✓ | ✓ |
| SI7006A20 (temp + hum) | ✓ | ✓ | ✓ |
| LTR329ALS01 (luminosidad) | ✓ | ✓ | ✓ |
| MPL3115A2 (presión) | ✓ | — | ✓ |
| LIS2HH12 (acelerómetro) | ✓ | — | — |
| PN532 NFC | — | ✓ | — |
| BLE scanner (integrado) | — | — | ✓ |
| LED externo RGB (protoboard) | ✓ | ✓ | ✓ |

---

## Payload Cayenne LPP por nodo

### Nodo 1 — Salón (uplink ~30 bytes)

| Canal | Tipo LPP | Código | Dato |
|---|---|---|---|
| 1 | Temperature | 0x67 | Temperatura °C |
| 2 | Humidity | 0x68 | Humedad %RH |
| 3 | Luminosity | 0x65 | Luminosidad lux |
| 4 | Barometric Pressure | 0x73 | Presión hPa |
| 5 | Accelerometer | 0x71 | X/Y/Z en g |
| 6 | Digital Input | 0x00 | ID habitación (1) |

### Nodo 2 — Dormitorio (uplink ~21 bytes)

| Canal | Tipo LPP | Código | Dato |
|---|---|---|---|
| 1 | Temperature | 0x67 | Temperatura °C |
| 2 | Humidity | 0x68 | Humedad %RH |
| 3 | Luminosity | 0x65 | Luminosidad lux |
| 4 | Analog Input | 0x02 | UID NFC parcial (÷100) |
| 5 | Digital Input | 0x00 | ID habitación (2) |

### Nodo 3 — Exterior (uplink ~25 bytes)

| Canal | Tipo LPP | Código | Dato |
|---|---|---|---|
| 1 | Temperature | 0x67 | Temperatura °C |
| 2 | Humidity | 0x68 | Humedad %RH |
| 3 | Barometric Pressure | 0x73 | Presión hPa |
| 4 | Digital Input | 0x00 | Dispositivos BLE cercanos |
| 5 | Digital Input | 0x00 | ID habitación (3) |

---

## Protocolo de downlinks (Fiware → TTN → LoPy4)

| Byte 0 | Comando | Bytes adicionales | Efecto en LED |
|---|---|---|---|
| 0x01 | Set LED color | R, G, B (0-255) | Color fijo |
| 0x02 | Parpadear LED | R, G, B (0-255) | Parpadeo 3× |
| 0x03 | Acceso NFC OK | — | Verde 2× |
| 0x04 | Acceso NFC denegado | — | Rojo 3× rápido |
| 0x05 | Alerta aforo BLE | — | Amarillo 4× |
| 0x06 | Alerta temperatura | 0x00=frío / 0x01=calor | Azul o naranja |
| 0x07 | Alerta exterior | — | Blanco 2× |

---

## Modelo de datos NGSI-v2

### Entidades y relaciones

```
House:001
  ├── Room:salon      ← Sensor:s1 (nodo 1)
  ├── Room:dormitorio ← Sensor:s2 (nodo 2, NFC)
  └── Room:exterior   ← Sensor:s3 (nodo 3, BLE)

Alert:temp_high       ← active, message, refSensor, timestamp
Alert:temp_low
Alert:humidity
Alert:vibration
Alert:nfc_denied
Alert:aforo
Alert:pressure_low

AccessLog:N           ← nfcUID, authorized, refSensor, timestamp
  (una entidad nueva por cada lectura NFC)
```

### Atributos de Sensor:s2 (control NFC)

```json
{
  "nfcAuthorizedUIDs": "A1B2C3D4,DEADBEEF",
  "nfcDetected": true,
  "nfcUidPartial": 41162
}
```

Para añadir un UID autorizado sin tocar código:
```bash
curl -X PATCH http://localhost:1026/v2/entities/Sensor:s2/attrs?options=keyValues \
  -H 'Content-Type: application/json' \
  -H 'fiware-service: smarthome' -H 'fiware-servicepath: /' \
  -d '{"nfcAuthorizedUIDs": "A1B2C3D4,DEADBEEF,NUEVOTARJETA"}'
```

---

## Automatizaciones implementadas (10 reglas)

| # | Condición | Acción Fiware | Downlink |
|---|---|---|---|
| 1 | `temperature > 28°C` | Activa `Alert:temp_high` | LED naranja al nodo |
| 2 | `temperature < 10°C` | Activa `Alert:temp_low` | LED azul al nodo |
| 3 | `humidity > 80%` | Activa `Alert:humidity` | — |
| 4 | `vibrationDetected == true` | Activa `Alert:vibration` | LED magenta al nodo |
| 5 | NFC UID detectado (autorizado) | Crea `AccessLog:N` authorized=true | LED verde nodo 2 |
| 6 | NFC UID detectado (denegado) | Crea `AccessLog:N` + `Alert:nfc_denied` | LED rojo nodo 2 |
| 7 | `bleDevicesNearby > 5` | Activa `Alert:aforo` | LED amarillo nodo 3 |
| 8 | `luminosity < 50 lux` en exterior | — | LED blanco nodo 3 |
| 9 | `barometricPressure < 1000 hPa` | Activa `Alert:pressure_low` | LED rojo parpadeante nodo 3 |
| 10 | Alerta desaparece (ej. temp vuelve a rango) | Desactiva la alerta en Orion | — |

---

## Estructura del proyecto

```
smart-home/
├── .gitignore
├── README.md
├── services                              # Gestión Docker (start/stop/reset)
│
├── lopy4/
│   ├── main.py                           # Bucle principal (3 nodos en uno)
│   ├── boot.py                           # Arranque del dispositivo
│   ├── led.py                            # Control LED interno + LEDs protoboard
│   ├── nfc.py                            # Driver PN532 por I²C (nodo dormitorio)
│   ├── ble_scanner.py                    # Escáner BLE integrado (nodo exterior)
│   ├── actuadores.py                     # Control de relés GPIO (expansión futura)
│   ├── credentials.example.py            # Plantilla credenciales TTN (subir a Git)
│   ├── credentials.py                    # Credenciales reales (NO subir a Git)
│   ├── pymakr.conf                       # Config extensión Pymakr VS Code
│   ├── ttn_payload_formatter.js          # Decoder/encoder para TTN Console
│   └── lib/
│       ├── CayenneLPP.py
│       ├── SI7006A20.py                  # Temp + Humedad
│       ├── LTR329ALS01.py                # Luminosidad
│       ├── MPL3115A2.py                  # Presión + Altitud
│       ├── LIS2HH12.py                   # Acelerómetro 3 ejes
│       ├── pysense.py / pycoproc.py      # Placa de expansión Pysense
│       └── pytrack.py                    # (no usado, incluido por compatibilidad)
│
├── fiware/
│   ├── ngsi/
│   │   └── ngsi_crear_entidades.sh       # House, Rooms, Sensors, Alerts
│   ├── iot-agent/
│   │   └── iot_agent_setup.sh            # Servicios y dispositivos IoT Agent
│   └── subscriptions/
│       └── ngsi_subscripciones.sh        # 10 suscripciones NGSI-v2
│
├── docker/
│   ├── docker-compose.yml                # Orion + MongoDB + IoT Agent + Mosquitto
│   └── mosquitto/mosquitto.conf
│
├── scripts/
│   ├── notification_server.py            # Servidor Flask: 10 reglas + TTN downlinks
│   └── mqtt_simulator.py                 # Simulador sensores sin hardware
│
└── esp32/                                # Código alternativo ESP32+BME280 (referencia)
    └── ...
```

---

## Puesta en marcha

### 1 · Registrar los 3 dispositivos en TTN

Para cada LoPy4, en TTN Console → Applications → `casa-inteligente-iot` → End devices → Register:
- LoRaWAN 1.0.2 · EU868 · OTAA
- Copiar DevEUI, AppEUI, AppKey

### 2 · Configurar credenciales en cada LoPy4

```bash
cd lopy4
cp credentials.example.py credentials.py
# Editar credentials.py con los valores de TTN y el NODE_TYPE correcto:
#   NODE_TYPE = 'salon'      ← nodo 1
#   NODE_TYPE = 'dormitorio' ← nodo 2
#   NODE_TYPE = 'exterior'   ← nodo 3
```

### 3 · Configurar Payload Formatter en TTN

TTN Console → Applications → Payload formatters → Uplink → Custom Javascript
→ Pegar contenido de `lopy4/ttn_payload_formatter.js`

Test uplink nodo salón:
```
01 67 00 E7 02 68 6E 03 65 01 5E 04 73 27 94 05 71 00 0A FF F6 03 E8 06 00 01
```
Resultado esperado: `temperature: 23.1, humidity: 55.0, luminosity: 350, barometricPressure: 1013.2, room: "salon"`

### 4 · Subir código a los LoPy4

Abrir carpeta `lopy4/` en VS Code con extensión Pymakr → Upload project to device
→ Verificar join en TTN Console → Live data

### 5 · Arrancar el stack Fiware

```bash
./services start
bash fiware/ngsi/ngsi_crear_entidades.sh
bash fiware/iot-agent/iot_agent_setup.sh
bash fiware/subscriptions/ngsi_subscripciones.sh
```

### 6 · Configurar el servidor de automatización

Editar `scripts/notification_server.py`:
```python
TTN_API_KEY = "NNSXS.TU_API_KEY_AQUI"
SENSOR_TO_TTN = {
    "Sensor:s1": "lopy4-salon",       # End device ID en TTN
    "Sensor:s2": "lopy4-dormitorio",
    "Sensor:s3": "lopy4-exterior",
}
```

Obtener API key: TTN Console → Applications → API keys → Generate
→ Marcar permiso: `Write downlink application traffic`

```bash
pip install flask requests
python3 scripts/notification_server.py
```

### 7 · Configurar UIDs NFC autorizados

```bash
curl -X PATCH http://localhost:1026/v2/entities/Sensor:s2/attrs?options=keyValues \
  -H 'Content-Type: application/json' \
  -H 'fiware-service: smarthome' -H 'fiware-servicepath: /' \
  -d '{"nfcAuthorizedUIDs": "UID1,UID2,UID3"}'
```

Para obtener el UID de una tarjeta, acércala al nodo 2 y observa
el log del `notification_server.py`: aparecerá el UID detectado.

---

## Conexión hardware

### LEDs externos en protoboard (los 3 nodos)

```
LoPy4 P2 → R 220Ω → LED rojo   → GND
LoPy4 P3 → R 220Ω → LED verde  → GND
LoPy4 P4 → R 220Ω → LED azul   → GND
```

### PN532 NFC (nodo dormitorio)

Configurar el módulo PN532 en modo I²C (interruptores DIP: SW1=OFF SW2=ON):
```
PN532 SDA → LoPy4 P9
PN532 SCL → LoPy4 P10
PN532 VCC → 3.3V
PN532 GND → GND
```

---

## Comandos de verificación

```bash
# Estado de todos los sensores
curl -s "http://localhost:1026/v2/entities?type=Sensor&options=keyValues" \
  -H 'fiware-service: smarthome' | python3 -m json.tool

# Alertas activas
curl -s "http://localhost:5000/alerts"

# Historial de accesos NFC
curl -s "http://localhost:5000/access-log"

# Enviar downlink manual (LED verde al nodo dormitorio)
curl -s "http://localhost:1026/v2/entities/Sensor:s2/attrs?options=keyValues" \
  -X PATCH \
  -H 'Content-Type: application/json' \
  -H 'fiware-service: smarthome' -H 'fiware-servicepath: /' \
  -d '{"ledCommand": "nfc_ok"}'

# Salud del servidor
curl -s "http://localhost:5000/health"
```

---

## Credenciales — gestión con múltiples dispositivos

Cada LoPy4 tiene su propio `credentials.py` (no en Git). El repositorio
incluye `credentials.example.py` como plantilla. El `NODE_TYPE` es la única
diferencia entre los tres dispositivos — el código `main.py` es idéntico
en los tres.

| Fichero | En Git | Propósito |
|---|:---:|---|
| `credentials.example.py` | ✓ | Plantilla pública |
| `credentials.py` | ✗ | Claves reales de cada dispositivo |

---

## Librerías Pysense incluidas

Las librerías de la carpeta `lopy4/lib/` son las librerías oficiales
de Pycom para la placa Pysense. No requieren instalación adicional:
se suben al dispositivo junto con el resto del código via Pymakr.
