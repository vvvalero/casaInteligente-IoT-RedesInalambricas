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
                 │   decodeUplink /       │
                 │   encodeDownlink       │
                 └────────────┬───────────┘
                              │ HTTP Webhook (JSON)
                 ┌────────────▼───────────────────────────┐
                 │         FIWARE STACK (Docker)           │
                 │  IoT Agent → Orion Context Broker       │
                 │  Sensor:s1/s2/s3 · Alert:* · AccessLog │
                 └────────────┬───────────────────────────┘
                              │ Suscripciones NGSI-v2
                              ▼
                 ┌────────────────────────┐
                 │  notification_server   │──► TTN API ──► Downlink LoPy4
                 │  8 automatizaciones    │
                 └────────────────────────┘
```

---

## Requisitos previos

- **Hardware**: 3× LoPy4 + Pysense, módulo PN532 NFC, LEDs y resistencias 220Ω, protoboard
- **Software**: VS Code + extensión Pymakr, WSL2 con Ubuntu, Docker Engine
- **Cuentas**: The Things Network (gratuita en [eu1.cloud.thethings.network](https://eu1.cloud.thethings.network))

---

## Puesta en marcha — paso a paso

### PARTE 1 · The Things Network (TTN)

#### Paso 1 · Crear la aplicación en TTN

1. Inicia sesión en TTN Console → **Applications** → **+ Create application**
2. Application ID: `casa-inteligente-iot` → **Create application**

#### Paso 2 · Registrar los 3 dispositivos

Repite para cada LoPy4 → **End devices** → **+ Register end device**:

| Campo | Valor |
|---|---|
| Registration method | Enter end device specifics manually |
| LoRaWAN version | LoRaWAN Specification **1.0.2** |
| Regional parameters | RP001 Regional Parameters 1.0.2 |
| Frequency plan | Europe 863-870 MHz (SF9 for RX2) |
| DevEUI | (leer del dispositivo con `LoRa().mac()`) |
| AppEUI | (generar o usar el que ya tienes) |
| AppKey | (generar automáticamente) |

> ⚠️ Es crítico usar LoRaWAN **1.0.2** — versiones distintas harán fallar el join OTAA.

Anota para cada dispositivo: **DevEUI**, **AppEUI** y **AppKey**.

#### Paso 3 · Configurar el Payload Formatter

TTN Console → tu aplicación → **Payload formatters** → **Uplink** → **Custom Javascript formatter**
→ Pega el contenido de `lopy4/ttn_payload_formatter.js` → **Save changes**

Puedes verificarlo en la pestaña **Test** con este payload de ejemplo (nodo salón):
```
01 67 00 E7 02 68 6E 03 65 01 5E 04 73 27 94 05 71 00 0A FF F6 03 E8 06 00 01
```
Resultado esperado: `temperature: 23.1, humidity: 55.0, luminosity: 350, room: "salon"`

---

### PARTE 2 · LoPy4

#### Paso 4 · Instalar extensión Pymakr en VS Code

VS Code → Extensions → buscar **Pymakr** (de Pycom) → Install

#### Paso 5 · Configurar credenciales de cada dispositivo

```bash
cd lopy4
cp credentials.example.py credentials.py
```

Edita `credentials.py` con los valores de TTN y el tipo de nodo:

```python
APP_EUI     = binascii.unhexlify('TU_APP_EUI_SIN_ESPACIOS')
APP_KEY     = binascii.unhexlify('TU_APP_KEY_SIN_ESPACIOS')
NODE_TYPE   = 'salon'      # 'salon' | 'dormitorio' | 'exterior'
TX_INTERVAL = 60           # segundos entre envíos
```

> ⚠️ `credentials.py` está en `.gitignore` — nunca se sube a GitHub.
> Cada LoPy4 tiene su propio fichero con su `NODE_TYPE` correspondiente.

#### Paso 6 · Subir el código al LoPy4

1. Conecta el LoPy4 por USB
2. Abre la carpeta `lopy4/` en VS Code
3. En el panel Pymakr → **Upload project to device**
4. Abre el terminal serie y verifica que aparece el join:

```
=== Casa Inteligente IoT ===
Nodo: salon
Intentando join OTAA...
  Esperando join...
Join completado!
--- Ciclo salon ---
  T=25.2C H=43.0% Lux=36 P=941.1hPa
  Uplink enviado
```

Si el join no completa tras 20 intentos, revisa que las credenciales en
`credentials.py` coinciden exactamente con las de TTN Console, y que
el dispositivo está registrado como LoRaWAN 1.0.2.

Repite los pasos 5 y 6 para los otros dos LoPy4 cambiando `NODE_TYPE`.

#### Paso 7 · Verificar en TTN Live data

TTN Console → tu aplicación → **Live data** → deberías ver los uplinks llegando
con el payload ya decodificado en campos JSON (`temperature`, `humidity`, etc.).

---

### PARTE 3 · Fiware en WSL2

> Todos los comandos siguientes se ejecutan en una terminal **Ubuntu (WSL2)**.

#### Paso 8 · Clonar el repositorio

```bash
git clone https://github.com/tuusuario/smart-home-iot.git
cd smart-home-iot
```

#### Paso 9 · Arrancar el stack Docker

```bash
chmod +x services
./services start
```

Resultado esperado:
```
✔ Container smarthome-mongodb   Healthy
✔ Container smarthome-orion     Healthy
✔ Container smarthome-iot-agent Started
✔ Container smarthome-mosquitto Started
  Orion:     OK ✅  v3.10.1
  IoT Agent: OK ✅
  MQTT:      OK ✅  puerto 1883
```

Si aparece `Pool overlaps with other one on this address space`:
```bash
docker network rm fiware_default
./services start
```

#### Paso 10 · Crear entidades, registrar dispositivos y suscripciones

```bash
bash fiware/ngsi/ngsi_crear_entidades.sh
bash fiware/iot-agent/iot_agent_setup.sh
bash fiware/subscriptions/ngsi_subscripciones.sh
```

Los tres scripts deben devolver **HTTP 201** en todas las líneas.

#### Paso 11 · Configurar el servidor de automatización

Edita `scripts/notification_server.py` y rellena estas dos secciones:

```python
# Tu API key de TTN con permiso de downlink
# TTN Console → Applications → API keys → Generate → Write downlink
TTN_API_KEY = "NNSXS.TU_API_KEY_AQUI"

# End device IDs exactos de TTN Console → End devices
SENSOR_TO_TTN = {
    "Sensor:s1": "lopy4-salon",
    "Sensor:s2": "lopy4-dormitorio",
    "Sensor:s3": "lopy4-exterior",
}
```

Arranca el servidor:
```bash
bash scripts/arrancar_servidor.sh
```

El script gestiona el entorno virtual automáticamente. Resultado esperado:
```
Casa Inteligente IoT - Servidor de notificaciones
Servidor en http://0.0.0.0:5000
 * Running on http://127.0.0.1:5000
```

#### Paso 12 · Configurar UIDs NFC autorizados

Acerca una tarjeta NFC al nodo dormitorio y observa el log del servidor:
```
NFC UID=A1B2C3D4 authorized=False
```

Añade el UID a la lista de autorizados:
```bash
curl -X PATCH "http://localhost:1026/v2/entities/Sensor:s2/attrs?options=keyValues" \
  -H 'Content-Type: application/json' \
  -H 'fiware-service: smarthome' -H 'fiware-servicepath: /' \
  -d '{"nfcAuthorizedUIDs": "A1B2C3D4,OTROTARJETA"}'
```

---

### PARTE 4 · Conectar TTN con Fiware

#### Paso 13 · Exponer Fiware a internet con ngrok

En una nueva terminal WSL2:
```bash
# Instalar ngrok si no lo tienes
curl -sSL https://ngrok-agent.s3.amazonaws.com/ngrok.asc | sudo tee /etc/apt/trusted.gpg.d/ngrok.asc >/dev/null
echo "deb https://ngrok-agent.s3.amazonaws.com buster main" | sudo tee /etc/apt/sources.list.d/ngrok.list
sudo apt update && sudo apt install ngrok

# Autenticar (cuenta gratuita en ngrok.com)
ngrok config add-authtoken TU_TOKEN_NGROK

# Crear el túnel al IoT Agent
ngrok http 4041
```

Copia la URL HTTPS que aparece: `https://xxxx.ngrok-free.app`

#### Paso 14 · Crear el Webhook en TTN

TTN Console → tu aplicación → **Integrations** → **Webhooks** → **+ Add webhook** → **Custom webhook**:

| Campo | Valor |
|---|---|
| Webhook ID | `fiware-smarthome` |
| Base URL | `https://xxxx.ngrok-free.app/iot/ul` |
| Format | JSON |
| Uplink message | ✓ activar checkbox |
| Header 1 | `fiware-service: smarthome` |
| Header 2 | `fiware-servicepath: /` |

→ **Save changes**

#### Paso 15 · Verificar la cadena completa

Espera al siguiente uplink del LoPy4 y comprueba que los datos llegan a Orion:

```bash
curl -s "http://localhost:1026/v2/entities/Sensor:s1?options=keyValues" \
  -H 'fiware-service: smarthome' | python3 -m json.tool
```

Deberías ver `temperature`, `humidity`, `luminosity` etc. con valores reales.

---

## Comandos de verificación y gestión

```bash
# Estado de los 3 sensores en Orion
curl -s "http://localhost:1026/v2/entities?type=Sensor&options=keyValues" \
  -H 'fiware-service: smarthome' | python3 -m json.tool

# Alertas activas en este momento
curl -s "http://localhost:5000/alerts" | python3 -m json.tool

# Historial de accesos NFC
curl -s "http://localhost:5000/access-log" | python3 -m json.tool

# Estado del servidor de automatización
curl -s "http://localhost:5000/health"

# Parar el stack Docker
./services stop

# Reinicio completo (borra todos los datos)
./services reset
```

---

## Conexión hardware

### LEDs externos en protoboard (los 3 nodos)

```
LoPy4 P2 ──► R 220Ω ──► LED rojo  ──► GND
LoPy4 P3 ──► R 220Ω ──► LED verde ──► GND
LoPy4 P4 ──► R 220Ω ──► LED azul  ──► GND
```

### PN532 NFC (nodo dormitorio únicamente)

Configura el módulo en modo I²C: interruptores DIP **SW1=OFF, SW2=ON**

```
PN532 SDA ──► LoPy4 P9
PN532 SCL ──► LoPy4 P10
PN532 VCC ──► 3.3V
PN532 GND ──► GND
```

---

## Payload Cayenne LPP por nodo

### Nodo 1 — Salón (~30 bytes)

| Canal | Tipo | Código | Dato |
|---|---|---|---|
| 1 | Temperature | 0x67 | Temperatura °C |
| 2 | Humidity | 0x68 | Humedad %RH |
| 3 | Luminosity | 0x65 | Luminosidad lux |
| 4 | Barometric Pressure | 0x73 | Presión hPa |
| 5 | Accelerometer | 0x71 | Aceleración X/Y/Z en g |
| 6 | Digital Input | 0x00 | ID habitación (1) |

### Nodo 2 — Dormitorio (~21 bytes)

| Canal | Tipo | Código | Dato |
|---|---|---|---|
| 1 | Temperature | 0x67 | Temperatura °C |
| 2 | Humidity | 0x68 | Humedad %RH |
| 3 | Luminosity | 0x65 | Luminosidad lux |
| 4 | Analog Input | 0x02 | UID NFC parcial (÷100) |
| 5 | Digital Input | 0x00 | ID habitación (2) |

### Nodo 3 — Exterior (~25 bytes)

| Canal | Tipo | Código | Dato |
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

## Automatizaciones implementadas

| # | Condición | Acción en Orion | Downlink al nodo |
|---|---|---|---|
| 1 | `temperature > 28°C` | Activa `Alert:temp_high` | LED naranja |
| 2 | `temperature < 10°C` | Activa `Alert:temp_low` | LED azul |
| 3 | `humidity > 80%` | Activa `Alert:humidity` | — |
| 4 | `vibrationDetected == true` | Activa `Alert:vibration` | LED magenta |
| 5 | NFC UID autorizado | Crea `AccessLog:N` authorized=true | LED verde (nodo 2) |
| 6 | NFC UID denegado | Crea `AccessLog:N` + `Alert:nfc_denied` | LED rojo (nodo 2) |
| 7 | `bleDevicesNearby > 5` | Activa `Alert:aforo` | LED amarillo (nodo 3) |
| 8 | `luminosity < 50 lux` exterior | — | LED blanco (nodo 3) |

---

## Estructura del proyecto

```
smart-home/
├── .gitignore
├── README.md
├── services                              # Gestión Docker: start | stop | reset
│
├── lopy4/
│   ├── main.py                           # Bucle principal — soporta los 3 nodos
│   ├── boot.py                           # Arranque del dispositivo
│   ├── led.py                            # LED interno (estado) + LEDs protoboard
│   ├── nfc.py                            # Driver PN532 I²C (nodo dormitorio)
│   ├── ble_scanner.py                    # Escáner BLE integrado (nodo exterior)
│   ├── actuadores.py                     # Control relés GPIO (expansión futura)
│   ├── credentials.example.py            # Plantilla — SÍ se sube a Git
│   ├── credentials.py                    # Credenciales reales — NO se sube a Git
│   ├── pymakr.conf                       # Configuración extensión Pymakr
│   ├── ttn_payload_formatter.js          # Decoder/encoder Cayenne LPP para TTN
│   └── lib/                              # Librerías oficiales Pycom para Pysense
│       ├── CayenneLPP.py
│       ├── SI7006A20.py
│       ├── LTR329ALS01.py
│       ├── MPL3115A2.py
│       ├── LIS2HH12.py
│       └── pysense.py / pycoproc.py
│
├── fiware/
│   ├── ngsi/ngsi_crear_entidades.sh      # Crea House, Rooms, Sensors, Alerts
│   ├── iot-agent/iot_agent_setup.sh      # Registra servicios y dispositivos
│   └── subscriptions/ngsi_subscripciones.sh  # Crea las 8 suscripciones
│
├── docker/
│   ├── docker-compose.yml                # Orion + MongoDB + IoT Agent + Mosquitto
│   └── mosquitto/mosquitto.conf
│
└── scripts/
    ├── notification_server.py            # Servidor Flask: reglas + TTN downlinks
    ├── arrancar_servidor.sh              # Gestiona venv y arranca el servidor
    └── mqtt_simulator.py                 # Simulador de sensores sin hardware
```

---

## Modelo de datos NGSI-v2

```
House:001
  ├── Room:salon      ← Sensor:s1 (salón)
  ├── Room:dormitorio ← Sensor:s2 (NFC)
  └── Room:exterior   ← Sensor:s3 (BLE)

Alert:temp_high | temp_low | humidity | vibration | nfc_denied | aforo | pressure_low
AccessLog:N  ← una entidad nueva por cada lectura NFC (nfcUID, authorized, timestamp)
```

---

## Solución de problemas frecuentes

**Join OTAA no completa:**
Verifica que en TTN Console el dispositivo está registrado como LoRaWAN 1.0.2 (no 1.0.3 ni 1.1). La AppKey debe coincidir byte a byte.

**`Pool overlaps with other one on this address space`:**
```bash
docker network rm fiware_default && ./services start
```

**`externally-managed-environment` al instalar pip:**
Usa siempre `bash scripts/arrancar_servidor.sh` en lugar de pip directamente.

**Las suscripciones dan HTTP 400:**
Ocurre si los atributos (temperature, humidity...) no existen aún en las entidades. El script corregido no usa filtros `expression` — si persiste el error comprueba que Orion está corriendo con `./services status`.

**Presión baja dispara alerta incorrectamente:**
En Albacete la presión normal es ~941 hPa por la altitud. Ajusta el umbral en `notification_server.py`: cambia `p >= 1000` por `p >= 950`.