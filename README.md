# Casa Inteligente IoT — Proyecto Final
## Dispositivos y Redes Inalámbricos · LoRaWAN + Fiware + NGSI-v2

---

## Arquitectura del Sistema

```
┌─────────────────────────────────────────────────────────────────┐
│                    DISPOSITIVOS (LoPy4 + Pysense)               │
│                                                                 │
│  [Salón]    [Cocina]   [Dormitorio]  [Baño]   [Exterior]       │
│  Sensor s1  Sensor s2  Sensor s3    Sensor s4  Sensor s5       │
│  Lamp lamp1 Lamp lamp2 Lamp lamp3   Lamp lamp4 Lamp lamp5      │
│  AC   ac1   AC   ac2   AC   ac3     AC   ac4   AC   ac5        │
│                    [Alarma alarm001]                             │
└──────────────────────────┬──────────────────────────────────────┘
                           │ LoRaWAN OTAA EU868 · Cayenne LPP
                           ▼
              ┌────────────────────────┐
              │  The Things Network    │
              │  Network Server        │
              │  Application Server    │
              │  Payload Formatter     │
              └────────────┬───────────┘
                           │ HTTP Webhook (JSON)
                           ▼
    ┌──────────────────────────────────────────┐
    │            FIWARE STACK (Docker)         │
    │                                          │
    │  IoT Agent UL2.0 → Orion Context Broker  │
    │                         │                │
    │                      MongoDB             │
    └──────────────────────┬───────────────────┘
                           │ Suscripciones NGSI-v2
                           ▼
              ┌────────────────────────┐
              │  notification_server   │
              │  · Temp > 28 → AC ON   │
              │  · Temp < 18 → AC HEAT │
              │  · Presencia + oscuro  │
              │    → Luz ON            │
              │  · Humedad > 80 → log  │
              └────────────────────────┘
```

---

## Estructura del proyecto

```
smart-home/
├── .gitignore
├── README.md
├── services                          # Script arranque/parada Docker
│
├── lopy4/
│   ├── main.py                       # Bucle principal
│   ├── boot.py                       # Arranque del dispositivo
│   ├── credentials.example.py        # Plantilla de credenciales TTN
│   ├── credentials.py                # TUS credenciales (NO en GitHub)
│   ├── pymakr.conf                   # Config Pymakr
│   ├── ttn_payload_formatter.js      # Decoder/encoder para TTN
│   └── lib/                          # Librerías Pysense
│       ├── CayenneLPP.py
│       ├── SI7006A20.py
│       ├── LTR329ALS01.py
│       ├── pysense.py
│       └── ...
│
├── fiware/
│   ├── ngsi/
│   │   └── ngsi_crear_entidades.sh   # Crea entidades en Orion
│   ├── iot-agent/
│   │   └── iot_agent_setup.sh        # Registra servicios y dispositivos
│   └── subscriptions/
│       └── ngsi_subscripciones.sh    # Crea suscripciones NGSI-v2
│
├── docker/
│   ├── docker-compose.yml            # Stack Fiware completo
│   └── mosquitto/
│       └── mosquitto.conf
│
├── scripts/
│   ├── notification_server.py        # Receptor notificaciones + automatización
│   └── mqtt_simulator.py             # Simulador sensores (sin hardware)
│
└── esp32/                            # Código alternativo para ESP32+BME280
    ├── smart_home_esp32.ino
    ├── lmic_project_config.h
    └── ...
```

---

## Modelo de datos NGSI-v2

### Payload Cayenne LPP (LoPy4 → TTN)

| Canal | Tipo | Código | Bytes | Escala | Campo en TTN |
|-------|------|--------|-------|--------|--------------|
| 1 | Temperatura | 0x67 | 2 | ÷10 °C | `temperature` |
| 2 | Humedad | 0x68 | 1 | ÷2 %RH | `humidity` |
| 3 | Luminosidad | 0x65 | 2 | 1 lux | `luminosity` |
| 4 | Habitación | 0x00 | 1 | 1-5 | `room` |

### Entidades NGSI-v2 en Orion

```
House:001
  ├── Room:salon      ← Sensor:s1, Lamp:lamp1, AC:ac1
  ├── Room:cocina     ← Sensor:s2, Lamp:lamp2, AC:ac2
  ├── Room:dormitorio ← Sensor:s3, Lamp:lamp3, AC:ac3
  ├── Room:bano       ← Sensor:s4, Lamp:lamp4, AC:ac4
  ├── Room:exterior   ← Sensor:s5, Lamp:lamp5, AC:ac5
  └── Alarm:alarm001
```

---

## Puesta en marcha

### 1 · Configurar credenciales del LoPy4

```bash
cd lopy4
cp credentials.example.py credentials.py
# Editar credentials.py con los valores de TTN Console
```

### 2 · Configurar Payload Formatter en TTN

TTN Console → Applications → [tu-app] → Payload formatters → Uplink  
→ Custom Javascript → pegar contenido de `lopy4/ttn_payload_formatter.js`

### 3 · Subir código al LoPy4

Abrir carpeta `lopy4/` en VS Code con extensión Pymakr  
→ Upload project to device → verificar join en TTN Live data

### 4 · Arrancar Fiware

```bash
./services start
bash fiware/ngsi/ngsi_crear_entidades.sh
bash fiware/iot-agent/iot_agent_setup.sh
bash fiware/subscriptions/ngsi_subscripciones.sh
```

### 5 · Configurar Webhook en TTN

TTN Console → Integrations → Webhooks → + Add webhook → Custom  
- Base URL: `http://TU_IP:4041/iot/ul`
- Headers: `fiware-service: smarthome` · `fiware-servicepath: /`

### 6 · Arrancar servidor de automatizaciones

```bash
pip install flask requests
python3 scripts/notification_server.py
```

### Comandos de verificación

```bash
# Ver todas las entidades
curl -s http://localhost:1026/v2/entities?options=keyValues \
  -H 'fiware-service: smarthome' | python3 -m json.tool

# Encender lámpara del salón manualmente
curl -X PATCH http://localhost:1026/v2/entities/Lamp:lamp1/attrs?options=keyValues \
  -H 'Content-Type: application/json' \
  -H 'fiware-service: smarthome' -H 'fiware-servicepath: /' \
  -d '{"onOff": "ON"}'
```

---

## Credenciales — gestión con múltiples dispositivos

Cada LoPy4 físico tiene su propio fichero `credentials.py` con sus credenciales TTN únicas. Este fichero **nunca se sube a GitHub** (está en `.gitignore`).

El repositorio incluye `credentials.example.py` como plantilla. Para cada dispositivo nuevo:

1. Registra el dispositivo en TTN Console
2. Copia `credentials.example.py` → `credentials.py`
3. Rellena `APP_EUI`, `APP_KEY` y `DEVICE_ROOM`
4. Sube al dispositivo con Pymakr

---

## Librerías necesarias (Arduino IDE, solo para ESP32)

| Librería | Autor |
|----------|-------|
| MCCI LoRaWAN LMIC library | MCCI Catena |
| Adafruit BME280 Library | Adafruit |
| Adafruit Unified Sensor | Adafruit |
