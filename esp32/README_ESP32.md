# ESP32 + BME280 + LoRaWAN — Casa Inteligente IoT

## Estructura de ficheros

```
esp32/
├── smart_home_esp32.ino     ← Sketch principal (abrir con Arduino IDE)
├── lmic_project_config.h    ← Config LMIC (COPIAR a la carpeta del sketch)
├── include/
│   ├── config.h             ← Credenciales TTN y pines (EDITAR primero)
│   ├── sensor_bme280.h
│   ├── cayenne_lpp.h
│   ├── lorawan.h
│   └── actuadores.h
├── src/
│   ├── sensor_bme280.cpp
│   ├── cayenne_lpp.cpp
│   ├── lorawan.cpp
│   └── actuadores.cpp
└── ttn/
    └── ttn_cayenne_formatter.js  ← Pegar en TTN Console
```

---

## Paso 1 — Instalar librerías en Arduino IDE

Herramientas → Gestor de librerías → buscar e instalar:

| Librería | Autor | Para qué |
|---|---|---|
| `MCCI LoRaWAN LMIC library` | MCCI Catena | Stack LoRaWAN completo |
| `Adafruit BME280 Library` | Adafruit | Lectura del sensor |
| `Adafruit Unified Sensor` | Adafruit | Dependencia del anterior |

Instalar soporte ESP32 en Arduino IDE:
- Archivo → Preferencias → URLs adicionales:
  `https://raw.githubusercontent.com/espressif/arduino-esp32/gh-pages/package_esp32_index.json`
- Herramientas → Placa → Gestor de tarjetas → buscar `esp32` → instalar

---

## Paso 2 — Configurar credenciales TTN

Editar `include/config.h`:

```cpp
// Obtener de: TTN Console → End devices → [dispositivo] → Overview
// DevEUI y AppEUI: formato LSB (invertir el orden de bytes de lo que muestra TTN)
// AppKey: formato MSB (igual que TTN lo muestra)
#define DEVEUI  { 0xAA, 0xBB, ... }  // 8 bytes LSB
#define APPEUI  { 0x00, 0x00, ... }  // 8 bytes LSB
#define APPKEY  { 0x11, 0x22, ... }  // 16 bytes MSB

// Indicar la habitación de este dispositivo
#define DEVICE_ROOM      1           // 1=salón 2=cocina 3=dormitorio 4=baño 5=exterior
#define DEVICE_ROOM_NAME "salon"
```

---

## Paso 3 — Conexión hardware

### ESP32 ↔ Módulo LoRa SX1276

| SX1276 | ESP32 GPIO | Notas |
|--------|-----------|-------|
| SCK    | 5         | SPI Clock |
| MISO   | 19        | SPI MISO |
| MOSI   | 27        | SPI MOSI |
| NSS/CS | 18        | Chip Select |
| RST    | 14        | Reset |
| DIO0   | 26        | Interrupción TX/RX done |
| DIO1   | 33        | Interrupción RX timeout |
| DIO2   | 32        | Interrupción FHSS |
| VCC    | 3.3V      | NO conectar a 5V |
| GND    | GND       | |

> Si usas **TTGO LoRa32 v2.1**: estos pines ya están conectados internamente. Solo necesitas conectar los sensores externos.

### ESP32 ↔ BME280 (I²C)

| BME280 | ESP32 GPIO | Notas |
|--------|-----------|-------|
| SDA    | 21        | I²C datos |
| SCL    | 22        | I²C reloj |
| VCC    | 3.3V      | |
| GND    | GND       | |
| CSB    | 3.3V      | Fuerza modo I²C |
| SDO    | GND       | Dirección 0x76 (o 3.3V → 0x77) |

### Sensores adicionales

| Componente | Pin ESP32 | Notas |
|------------|----------|-------|
| PIR HC-SR501 (OUT) | 25 | Salida digital HIGH/LOW |
| PIR HC-SR501 (VCC) | 5V | Requiere 5V |
| LDR (divisor) | 34 (ADC1) | R pull-down 10kΩ a GND |

### Actuadores (relés)

| Relé | Pin ESP32 | Controla |
|------|----------|---------|
| Relé 1 IN | 13 | Lámpara |
| Relé 2 IN | 12 | Aire acondicionado |
| Relé 3 IN | 4  | Alarma / buzzer |

> Los módulos de relé optoacoplados funcionan con 3.3V en el pin IN del ESP32.

---

## Paso 4 — Registrar el dispositivo en TTN

1. TTN Console → Applications → `+ Create application`
2. Dentro de la app → End devices → `+ Register end device`
3. Seleccionar: `Enter end device specifics manually`
   - LoRaWAN version: `LoRaWAN Specification 1.0.3`
   - Regional parameters: `RP001 Regional Parameters 1.0.3 revision A`
   - Frequency plan: `Europe 863-870 MHz (SF9 for RX2 - recommended)`
4. DevEUI: pegar el valor de tu dispositivo (o generar uno nuevo)
5. AppEUI: generar o usar `0000000000000000`
6. AppKey: generar automáticamente
7. Copiar los tres valores a `config.h`

---

## Paso 5 — Configurar Payload Formatter en TTN

1. TTN Console → Applications → [tu-app] → Payload formatters
2. Uplink → `Custom Javascript formatter`
3. Pegar el contenido de `ttn/ttn_cayenne_formatter.js`
4. Guardar y probar con el hex: `01 67 00 E7 02 68 6E 03 73 27 94 04 65 01 5E 05 66 01`

Resultado esperado:
```json
{
  "temperature": 23.1,
  "humidity": 55.0,
  "barometricPressure": 1013.2,
  "luminosity": 350,
  "presence": true
}
```

---

## Paso 6 — Compilar y subir

1. Abrir `smart_home_esp32.ino` en Arduino IDE
2. Herramientas → Placa → `TTGO LoRa32-OLED v2.1` (o `ESP32 Dev Module`)
3. Herramientas → Puerto → seleccionar el COM del ESP32
4. Herramientas → Upload Speed → `115200`
5. Subir (Ctrl+U)
6. Abrir Monitor Serie (115200 baud) y verificar:

```
================================
  Casa Inteligente IoT v1.0.0
  Habitación: salon
  Intervalo TX: 900 s
================================
[BME280] Sensor inicializado correctamente (0x76)
[LoRaWAN] LMIC inicializado (EU868)
[LoRaWAN] Iniciando join OTAA...
[LoRaWAN] ✓ Join OTAA completado
[BME280] T=23.1°C  H=55.0%  P=1013.2 hPa
[LPP] Buffer (15 bytes): 01 67 00 E7 02 68 6E 03 73 27 94 04 65 01 5E 05 66 01
[LoRaWAN] TX encolado (15 bytes, puerto 1, SF7)
[LoRaWAN] Transmitiendo...
[LoRaWAN] TX completado
```

---

## Formato de payload Cayenne LPP

Cada mensaje uplink tiene esta estructura (15 bytes para 5 campos):

```
01 67 00 E7   → Canal 1, Temperatura, 23.1°C  (0x00E7 = 231 ÷ 10)
02 68 6E      → Canal 2, Humedad, 55.0%RH     (0x6E = 110 ÷ 2)
03 73 27 94   → Canal 3, Presión, 1013.2hPa   (0x2794 = 10132 ÷ 10)
04 65 01 5E   → Canal 4, Luminosidad, 350lux  (0x015E = 350)
05 66 01      → Canal 5, Presencia, detectada (0x01 = 1)
```

## Comandos downlink

Enviar desde TTN Console → End device → Messaging → Downlink:

```json
{ "frm_payload": "AQE=", "f_port": 1 }   → luz ON  (0x01 0x01 en base64)
{ "frm_payload": "AgA=", "f_port": 1 }   → AC  OFF (0x02 0x00 en base64)
{ "frm_payload": "AwE=", "f_port": 1 }   → alarma ON
```

O usando el Payload Formatter downlink con:
```json
{ "comando": "luz", "valor": 1 }
```
