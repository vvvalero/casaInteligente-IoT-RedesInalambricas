# Casa Inteligente IoT — Proyecto Final
## Dispositivos y Redes Inalámbricos · LoRaWAN + Fiware + NGSI-v2

---

## Arquitectura del sistema

```
┌──────────────────────────────────────────────────────────────────┐
│                       3× LoPy4 + Pysense                        │
│                                                                  │
│  Nodo 1 — Salón          Nodo 2 — Dormitorio   Nodo 3 — Exterior │
│  SI7006A20 (T+H)         SI7006A20 (T+H)       SI7006A20 (T+H)  │
│  LTR329ALS01 (lux)       LTR329ALS01 (lux)     MPL3115A2 (pres) │
│  MPL3115A2 (presión)     BLE scanner (NFC)     BLE scanner      │
│  LIS2HH12 (aceleróm.)    LED RGB integrado      LED RGB integrado │
│                          ▲                                       │
│                    BLE Advertising                               │
│                    (Mfr. Specific Data)                          │
│                          │                                       │
│               ┌──────────┴──────────┐                           │
│               │  ESP32 + PN532 NFC  │                           │
│               │  (I²C en protoboard)│                           │
│               └─────────────────────┘                           │
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
                              │ HTTPS Webhook → api.vvalero.dev
                 ┌────────────▼───────────────────────────┐
                 │         FIWARE STACK (Docker)           │
                 │                                        │
                 │  Nginx (proxy TLS) → IoT Agent         │
                 │  IoT Agent → Orion Context Broker      │
                 │                    │                   │
                 │  Sensor:s1/s2/s3   MongoDB             │
                 │  Alert:*           AccessLog:N          │
                 └────────────┬───────────────────────────┘
                              │ Suscripciones NGSI-v2
                              ▼
                 ┌────────────────────────┐
                 │  notification_server   │──► TTN API ──► Downlink LoPy4
                 │  8 automatizaciones    │
                 └────────────────────────┘
```

---

## Despliegue

El sistema soporta dos modos de despliegue:

| Modo | Cuándo usarlo | Comando |
|---|---|---|
| **Local (WSL2)** | Desarrollo y pruebas | `./services start` |
| **DMZ Universidad** | Demo y producción | `./services_dmz start` |

En el modo DMZ, el sistema se expone en `https://api.vvalero.dev` con certificado TLS automático (Let's Encrypt). El subdominio `api.vvalero.dev` apunta mediante registro DNS tipo A a la IP pública de la VM universitaria.

---

## Requisitos previos

- **Hardware**: 3× LoPy4 + Pysense, 1× ESP32, módulo PN532 NFC (para nodo dormitorio)
- **Software**: VS Code + extensión Pymakr, WSL2 Ubuntu, Docker Engine
- **Cuentas**: The Things Network — [eu1.cloud.thethings.network](https://eu1.cloud.thethings.network)

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
| DevEUI | (leer del dispositivo — aparece en el log de arranque) |
| AppEUI | (generar o usar el que ya tienes) |
| AppKey | (generar automáticamente) |

> ⚠️ Es crítico usar LoRaWAN **1.0.2** — otras versiones harán fallar el join OTAA.

Anota para cada dispositivo: **DevEUI**, **AppEUI** y **AppKey**.

#### Paso 3 · Configurar el Payload Formatter

TTN Console → tu aplicación → **Payload formatters** → **Uplink** → **Custom Javascript formatter**
→ Pega el contenido de `lopy4/ttn_payload_formatter.js` → **Save changes**

Verifica en la pestaña **Test** con este payload de ejemplo (nodo salón):
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
TX_INTERVAL = 30           # segundos entre envíos (respuesta rápida a eventos)
                           # TTN Fair Use: 30s = ~48 min airtime/día (OK)
                           # Opciones: 20s (rápido), 30s (recomendado), 60s (lento)

# Solo para el nodo dormitorio — ver Paso 6b
ESP32_NFC_MAC = 'AA:BB:CC:DD:EE:FF'
```

> ⚠️ `credentials.py` está en `.gitignore` — nunca se sube a GitHub.
> Cada LoPy4 tiene su propio fichero con su `NODE_TYPE` correspondiente.

#### Paso 6b · (Solo nodo dormitorio) Flashear el ESP32 y obtener su MAC

1. Abre `esp32/nfc_ble_broadcaster/nfc_ble_broadcaster.ino` en el Arduino IDE
2. Instala las librerías si no las tienes: **Gestor de librerías** → buscar `PN532` de Elechouse → instalar
3. Selecciona tu placa ESP32 y puerto → **Subir**
4. Abre el **Monitor Serie** a 115200 baud — aparecerá:
```
[NFC] PN532 v1.6
[BLE] Anunciando. MAC: aa:bb:cc:dd:ee:ff
[SYS] Listo — esperando tarjetas NFC...
```
5. Copia esa MAC en `credentials.py` del nodo dormitorio:
```python
ESP32_NFC_MAC = 'AA:BB:CC:DD:EE:FF'   # en mayúsculas
```

> El ESP32 se conecta al PN532 por I²C: SDA→GPIO21, SCL→GPIO22, RST→GPIO32.
> DIP switches del PN532: SW1=OFF, SW2=ON (modo I²C).

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

Si el join no completa, verifica que las credenciales coinciden exactamente con TTN Console y que el dispositivo está registrado como LoRaWAN 1.0.2.

Repite los pasos 5 y 6 para los otros dos LoPy4 cambiando `NODE_TYPE`.

#### Paso 7 · Verificar en TTN Live data

TTN Console → tu aplicación → **Live data** → los uplinks deben llegar con el payload decodificado en JSON (`temperature`, `humidity`, `room`, etc.).

---

### PARTE 3 · Fiware en WSL2 (desarrollo local)

> Todos los comandos se ejecutan en una terminal **Ubuntu (WSL2)**.

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

Todos los scripts deben devolver **HTTP 201** en todas las líneas.

> La suscripción `[8] Acceso NFC` dará HTTP 400 la primera vez — es normal.
> El tipo `AccessLog` no existe hasta el primer acceso NFC. Se creará automáticamente.

#### Paso 11 · Configurar el servidor de automatización

Edita `scripts/notification_server.py` y rellena:

```python
TTN_API_KEY = "NNSXS.TU_API_KEY_AQUI"
# TTN Console → Applications → API keys → Generate
# Permiso necesario: "Write downlink application traffic"
```

Los Device IDs ya tienen los valores por defecto correctos:
```python
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

El script crea el entorno virtual automáticamente. Resultado esperado:
```
Casa Inteligente IoT - Servidor de notificaciones
Servidor en http://0.0.0.0:5000
 * Running on http://127.0.0.1:5000
```

#### Paso 12 · Configurar UIDs NFC autorizados

Acerca una tarjeta NFC al nodo dormitorio y observa el log del servidor — aparecerá el UID detectado. Añádelo a la lista de autorizados:

```bash
curl -X PATCH "http://localhost:1026/v2/entities/Sensor:s2/attrs?options=keyValues" \
  -H 'Content-Type: application/json' \
  -H 'fiware-service: smarthome' -H 'fiware-servicepath: /' \
  -d '{"nfcAuthorizedUIDs": "A1B2C3D4,OTROTARJETA"}'
```

---

### PARTE 4 · Conectar TTN con Fiware

#### Paso 13 · Exponer el IoT Agent a internet con ngrok (desarrollo local)

```bash
# Instalar ngrok
curl -sSL https://ngrok-agent.s3.amazonaws.com/ngrok.asc \
  | sudo tee /etc/apt/trusted.gpg.d/ngrok.asc >/dev/null
echo "deb https://ngrok-agent.s3.amazonaws.com buster main" \
  | sudo tee /etc/apt/sources.list.d/ngrok.list
sudo apt update && sudo apt install ngrok

# Autenticar (cuenta gratuita en ngrok.com)
ngrok config add-authtoken TU_TOKEN_NGROK

# Crear el túnel al IoT Agent
ngrok http 4041
```

Copia la URL HTTPS: `https://xxxx.ngrok-free.app`

> En el DMZ universitario este paso no es necesario — se usa `https://api.vvalero.dev` directamente.

#### Paso 14 · Crear el Webhook en TTN

TTN Console → tu aplicación → **Integrations** → **Webhooks** → **+ Add webhook** → **Custom webhook**:

| Campo | Valor (local) | Valor (DMZ) |
|---|---|---|
| Webhook ID | `fiware-smarthome` | `fiware-smarthome` |
| Base URL | `https://xxxx.ngrok-free.app/iot/ul` | `https://api.vvalero.dev/iot/ul` |
| Format | JSON | JSON |
| Uplink message | ✓ | ✓ |
| Header 1 | `fiware-service: smarthome` | `fiware-service: smarthome` |
| Header 2 | `fiware-servicepath: /` | `fiware-servicepath: /` |

#### Paso 15 · Verificar la cadena completa

Espera al siguiente uplink del LoPy4 y comprueba que los datos llegan a Orion:

```bash
curl -s "http://localhost:1026/v2/entities/Sensor:s1?options=keyValues" \
  -H 'fiware-service: smarthome' | python3 -m json.tool
```

Deberías ver `temperature`, `humidity`, `luminosity` etc. con valores reales y actualizándose.

---

### PARTE 5 · Despliegue en DMZ universitario

> Solo necesario para exposición pública en `api.vvalero.dev`.

#### Paso 16 · Configurar el registro DNS

En Vercel → `vvalero.dev` → DNS Records → añadir:

| Tipo | Nombre | Valor |
|---|---|---|
| A | api | IP pública de la VM universitaria |

#### Paso 17 · Preparar credenciales en la VM

```bash
cp .env.example .env
nano .env   # rellenar TTN_API_KEY y device IDs
```

#### Paso 18 · Ejecutar el setup automático

```bash
bash scripts/setup_dmz.sh
```

El script verifica el DNS, obtiene el certificado TLS y arranca el stack completo.

#### Paso 19 · Inicializar Fiware en el DMZ

```bash
bash fiware/ngsi/ngsi_crear_entidades.sh
bash fiware/iot-agent/iot_agent_setup.sh
bash fiware/subscriptions/ngsi_subscripciones.sh
```

#### Paso 20 · Actualizar el webhook en TTN

Cambiar la Base URL del webhook a `https://api.vvalero.dev/iot/ul` (ver Paso 14).

---

## Conexión hardware

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

El LED RGB integrado del LoPy4 actúa como actuador visible. Fiware envía
downlinks que cambian su color según el evento detectado.

| Byte 0 | Comando | Bytes adicionales | Efecto en LED integrado |
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
├── .env.example                          # Plantilla variables de entorno (DMZ)
├── .gitignore
├── README.md
├── services                              # Gestión Docker local: start|stop|reset
├── services_dmz                          # Gestión Docker DMZ:   start|stop|reset
│
├── esp32/
│   └── nfc_ble_broadcaster/
│       └── nfc_ble_broadcaster.ino       # ESP32: lee PN532 y emite UID por BLE advertising
│
├── lopy4/
│   ├── main.py                           # Bucle principal — soporta los 3 nodos
│   ├── boot.py                           # Arranque del dispositivo
│   ├── led.py                            # Control LED RGB integrado del LoPy4
│   ├── nfc.py                            # Driver PN532 I²C (reservado / no usado activamente)
│   ├── ble_scanner.py                    # Escáner BLE: aforo (exterior) + NFC via ESP32 (dormitorio)
│   ├── credentials.example.py            # Plantilla — SÍ se sube a Git
│   ├── credentials.py                    # Credenciales reales — NO se sube a Git
│   ├── pymakr.conf                       # Configuración extensión Pymakr
│   ├── ttn_payload_formatter.js          # Decoder/encoder Cayenne LPP para TTN
│   └── lib/                              # Librerías oficiales Pycom para Pysense
│       ├── CayenneLPP.py
│       ├── SI7006A20.py                  # Temp + Humedad
│       ├── LTR329ALS01.py                # Luminosidad
│       ├── MPL3115A2.py                  # Presión + Altitud
│       ├── LIS2HH12.py                   # Acelerómetro 3 ejes
│       └── pysense.py / pycoproc.py      # Placa de expansión Pysense
│
├── fiware/
│   ├── ngsi/ngsi_crear_entidades.sh      # Crea House, Rooms, Sensors, Alerts
│   ├── iot-agent/iot_agent_setup.sh      # Registra los 3 nodos en IoT Agent
│   └── subscriptions/ngsi_subscripciones.sh  # Crea las 8 suscripciones
│
├── docker/
│   ├── docker-compose.yml                # Stack local: Orion+MongoDB+IoTAgent+Mosquitto
│   ├── docker-compose.dmz.yml            # Stack DMZ: añade Nginx+Certbot
│   ├── Dockerfile.notification           # Imagen del notification server (DMZ)
│   ├── mosquitto/mosquitto.conf
│   └── nginx/
│       ├── nginx.conf
│       └── conf.d/smarthome.conf         # Proxy inverso → api.vvalero.dev
│
└── scripts/
    ├── notification_server.py            # Servidor Flask: 8 reglas + TTN downlinks
    ├── arrancar_servidor.sh              # Gestiona venv y arranca el servidor (local)
    ├── setup_dmz.sh                      # Instalación automática en el DMZ
    ├── requirements.txt                  # Dependencias Python (Flask, requests)
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

## Comandos de verificación y gestión

```bash
# Estado de los 3 sensores en Orion
curl -s "http://localhost:1026/v2/entities?type=Sensor&options=keyValues" \
  -H 'fiware-service: smarthome' | python3 -m json.tool

# Alertas activas
curl -s "http://localhost:5000/alerts" | python3 -m json.tool

# Historial de accesos NFC
curl -s "http://localhost:5000/access-log" | python3 -m json.tool

# Estado del servidor
curl -s "http://localhost:5000/health"

# Parar el stack Docker
./services stop

# Reinicio completo (borra todos los datos)
./services reset

# Ver logs de un servicio concreto (DMZ)
./services_dmz logs orion
./services_dmz logs notification-server
```

---

## Solución de problemas frecuentes

**Join OTAA no completa:**
Verifica que en TTN Console el dispositivo está registrado como LoRaWAN Specification 1.0.2 (no 1.0.3 ni 1.1). La AppKey debe coincidir byte a byte con la de `credentials.py`.

**`Pool overlaps with other one on this address space`:**
```bash
docker network rm fiware_default && ./services start
```

**`externally-managed-environment` al instalar pip:**
Usa siempre `bash scripts/arrancar_servidor.sh` en lugar de pip directamente. El script gestiona el entorno virtual automáticamente.

**Suscripción [8] AccessLog da HTTP 400:**
Normal al primer arranque — el tipo `AccessLog` no existe hasta el primer acceso NFC. Se crea automáticamente y no requiere intervención.

**Presión baja dispara alerta incorrectamente:**
La presión normal en Albacete es ~941 hPa por la altitud (~700m). El umbral ya está corregido a 950 hPa en `notification_server.py`.


**Downlinks TTN dan HTTP 400:**
La `TTN_API_KEY` no está configurada en `notification_server.py`. Generarla en TTN Console → Applications → API keys con permiso `Write downlink application traffic`.

**El nodo dormitorio nunca detecta tarjeta NFC:**
1. Verifica que el ESP32 está encendido y el Monitor Serie muestra `[SYS] Listo`.
2. Comprueba que `ESP32_NFC_MAC` en `credentials.py` coincide exactamente con la MAC impresa por el ESP32 (en mayúsculas con dos puntos: `AA:BB:CC:DD:EE:FF`).
3. Si el ESP32 muestra `[NFC] ERROR: PN532 no detectado`, revisa el cableado I²C y que los DIP switches del PN532 estén en SW1=OFF, SW2=ON.
4. Asegúrate de que el ESP32 está a menos de ~10 metros del LoPy4 durante el escaneo BLE.