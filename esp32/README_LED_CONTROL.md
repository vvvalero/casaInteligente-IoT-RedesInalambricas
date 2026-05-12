# Control de LEDs simples vía BLE — ESP32 NFC-BLE Broadcaster (6 indicadores)

## Descripción General

El ESP32 controla **6 indicadores de estado**, cada uno compuesto por **2 LEDs simples**:
- **Indicadores 1-3**: Estado de cada nodo (verde=OK, rojo=alerta)
- **Indicadores 4-5**: Alertas por tipo agregadas (temperatura y humedad)
- **Indicador 6**: Acceso NFC (verde=autorizado, rojo=denegado, apagado=sin actividad)

Los LEDs se actualizan automáticamente con lógica inteligente de agregación.

### Mapeo de Indicadores (6 totales, 12 LEDs)

| Indicador | GPIO alerta (A) | Color alerta | GPIO normal (B) | Color normal | Propósito |
|-----------|-----------------|--------------|-----------------|--------------|-----------|
| **1** | 25 | 🔴 Rojo | 26 | 🟢 Verde | **Nodo s1 (Salón)** |
| **2** | 12 | 🔴 Rojo | 13 | 🟢 Verde | **Nodo s2 (Dormitorio)** |
| **3** | 14 | 🔴 Rojo | 27 | 🟢 Verde | **Nodo s3 (Exterior)** |
| **4** | 15 | 🟠 Naranja | 2 | 🔵 Azul | **Temperatura (agregado)** |
| **5** | 4 | 🟠 Naranja | 16 | 🔵 Azul | **Humedad (agregado)** |
| **6** | 18 | 🔴 Rojo | 19 | 🟢 Verde | **Acceso NFC** |

**Lógica de colores:**
- Indicadores 1-3 (nodos): **Rojo** = alerta / **Verde** = OK
- Indicadores 4-5 (sensores): **Naranja** = alerta 1 nodo / **Ambos** = crítico (2+ nodos) / **Azul** = OK
- Indicador 6 (NFC): **Verde** = autorizado (auto-apaga en 1.5 s) / **Rojo** = denegado (auto-apaga en 2 s) / **Ambos** = esperando servidor / **Apagado** = sin actividad

---

## Estados de LEDs

### Indicadores 1-3 — Estado por Nodo

Cada indicador muestra el estado general del nodo:

```
Indicador 1: Nodo s1 (Salón)
Indicador 2: Nodo s2 (Dormitorio)
Indicador 3: Nodo s3 (Exterior)
```

**Estados:**
- 🟢 **Verde** — Todo OK en ese nodo (LED verde encendido)
- 🔴 **Rojo** — Hay alguna alerta en ese nodo (LED rojo encendido)

**Ejemplo:**
```
Si s1 tiene temperatura alta:    Indicador 1 = Rojo
Si s2 está normal:               Indicador 2 = Verde
Si s3 tiene otra alerta:         Indicador 3 = Rojo
```

### Indicadores 4-5 — Alertas por Tipo (Agregadas de todos los nodos)

Cada indicador muestra si hay ese tipo de alerta en algún nodo:

```
Indicador 4: Temperatura (temp alta o baja en cualquier nodo)
Indicador 5: Humedad (humedad alta en cualquier nodo)
```

**Estados:**
- 🔵 **Azul** — OK en todos los nodos (solo LED normal encendido)
- 🟠 **Naranja** — Alerta en 1 nodo (solo LED alerta encendido)
- 🟡 **Amarillo** — Alerta en 2+ nodos (ambos LEDs encendidos = crítico)

**Ejemplo:**
```
Si s1 tiene temp alta y s2 tiene temp baja:
  Indicador 4 = Amarillo (crítico: 2 nodos con alerta de temperatura)

Si todos OK:
  Indicador 5 = Azul
```

### Indicador 6 — Acceso NFC

Muestra el resultado del último intento de acceso con tarjeta NFC. Se apaga automáticamente tras un breve tiempo.

**Estados:**
- ⚫ **Apagado** — Sin actividad NFC reciente
- 🟡 **Amarillo** — Tarjeta leída, esperando respuesta del servidor
- 🟢 **Verde** — Último acceso autorizado (auto-apaga en 1.5 s)
- 🔴 **Rojo** — Último acceso denegado (auto-apaga en 2 s)

**Ejemplo:**
```
Sin tarjetas leídas:         Indicador 6 = Apagado
Tarjeta autorizada:          Indicador 6 = Verde → Apagado (1.5 s)
Tarjeta no reconocida:       Indicador 6 = Rojo  → Apagado (2 s)
```

---

## Protocolo BLE

### Servicio BLE
- **UUID**: `a6e3ed8d-6a2f-4a8b-9b8c-1c9f8e7d6c5b`

### Característica de Comando LED
- **UUID**: `b1d2e3f4-5a6b-7c8d-9e0f-a1b2c3d4e5f6`
- **Tipo**: Write
- **Formato**: 3 bytes: `[led_id][red_on][green_on]`
  - `led_id`: 1-6 (qué indicador)
  - `red_on`: 0 o 1 (encender LED alerta: rojo o naranja según indicador)
  - `green_on`: 0 o 1 (encender LED normal: verde o azul según indicador)

### Ejemplo de Comandos

```
Indicador 1 (s1) rojo:                [0x01, 0x01, 0x00]
Indicador 2 (s2) verde:               [0x02, 0x00, 0x01]
Indicador 3 (s3) amarillo (crítico):  [0x03, 0x01, 0x01]
Indicador 4 (Temp) naranja:           [0x04, 0x01, 0x00]
Indicador 4 (Temp) amarillo:          [0x04, 0x01, 0x01]
Indicador 5 (Humedad) azul:           [0x05, 0x00, 0x01]
Indicador 6 (NFC) autorizado:         [0x06, 0x00, 0x01]
Indicador 6 (NFC) denegado:           [0x06, 0x01, 0x00]
Indicador 6 (NFC) esperando:          [0x06, 0x01, 0x01]
Indicador 6 (NFC) sin actividad:      [0x06, 0x00, 0x00]
```

Los comandos se envían automáticamente desde `notification_server.py` mediante la clase `LEDStateManager`, que calcula el estado correcto de cada indicador según las alertas activas.

---

## Hardware — Conexiones

### PN532 (NFC)
```
PN532 SDA → GPIO 21
PN532 SCL → GPIO 22
PN532 VCC → 3.3V
PN532 GND → GND
PN532 RST → GPIO 32
```

### LEDs Simples (on/off, 5mm)
Cada indicador necesita:
- 1 LED alerta (rojo o naranja): ánodo → GPIO, cátodo → GND con resistencia
- 1 LED normal (verde o azul): ánodo → GPIO, cátodo → GND con resistencia
- Resistencia por LED: ~220Ω (para ~20mA a 2V)

**Pines usados (12 total, 2 por indicador):**
```
Indicador 1 (s1):         GPIO 25 (ROJO),    GPIO 26 (VERDE)
Indicador 2 (s2):         GPIO 12 (ROJO),    GPIO 13 (VERDE)
Indicador 3 (s3):         GPIO 14 (ROJO),    GPIO 27 (VERDE)
Indicador 4 (Temp):       GPIO 15 (NARANJA), GPIO 2  (AZUL)
Indicador 5 (Humedad):    GPIO 4  (NARANJA), GPIO 16 (AZUL)
Indicador 6 (Acceso NFC): GPIO 18 (ROJO),    GPIO 19 (VERDE)
```

**Reservados (no disponibles):**
- GPIO 21, 22: I²C para PN532
- GPIO 32: Reset del PN532
- GPIO 6-11: SPI flash interna (NO USAR)
- GPIO 34-39: Solo entrada, sin salida digital

---

## Software — Arduino

### Librerías Necesarias
Instala en Arduino IDE (Sketch → Include Library → Manage Libraries):

1. **PN532** de Elechouse
   - Busca: "elechouse/PN532"
   - Versión: 1.4.6 o superior

2. **ESP32 BLE Arduino**
   - Incluida en el paquete esp32 de Espressif
   - Instala el paquete: "esp32" en Tools → Board Manager

### Compilación
```bash
# En Arduino IDE:
Tools → Board → esp32 → ESP32 Dev Module
Tools → Port → /dev/ttyUSB0 (o similar)
Sketch → Upload
```

---

## Software — Backend Python

### Instalación
```bash
pip install bleak==0.21.1
```

Verifica que `requirements.txt` contenga:
```
bleak==0.21.1
```

### Configuración
El servidor busca automáticamente el ESP32 por nombre BLE: **"ESP32-NFC-Door"**

Si quieres cambiar el nombre, edita en `nfc_ble_broadcaster.ino`:
```cpp
BLEDevice::init("ESP32-NFC-Door");  // ← Cambiar aquí
```

Y en `notification_server.py`:
```python
_ble_client = BLELEDClient(device_name="ESP32-NFC-Door")  // ← Cambiar aquí
```

### Logs
El servidor mostrará:
```
[BLE] Cliente BLE iniciando...
[BLE] ESP32 encontrado: 5c:cf:7f:12:34:56
[BLE] Conectado a ESP32-NFC-Door
[BLE] Indicador 1 → ROJO (alerta)
```

Si hay error:
```
[BLE] bleak no instalada. Control BLE de LEDs desactivado.
```

---

## Solución de Problemas

### Los LEDs no se encienden
1. ✓ Verifica conexiones GPIO y alimentación (3.3V para GPIO, 5V para LEDs)
2. ✓ Comprueba que la resistencia de cada LED sea correcta (~220Ω)
3. ✓ Verifica que el LED esté bien conectado (lado largo = ánodo a GPIO)
4. ✓ Prueba manualmente: `digitalWrite(25, HIGH)` para el LED rojo del indicador 1

### El ESP32 no se detecta por BLE
1. ✓ Abre Monitor Serial y verifica que se inicialice correctamente
2. ✓ Busca manualmente: `BTLEScanner` o `nRFConnect` en móvil
3. ✓ Verifica que el servidor Python esté corriendo
4. ✓ Espera ~5 segundos, el cliente BLE busca con timeout de 5s

### Errores de compilación Arduino
1. ✓ Instala todas las librerías mencionadas
2. ✓ Selecciona placa ESP32 Dev Module correctamente
3. ✓ Verifica que GPIO 21/22 no entren en conflicto (I²C por defecto)

### El servidor no conecta al ESP32
1. ✓ Instala bleak: `pip install bleak`
2. ✓ Si está en Docker, bleak puede no funcionar bien (limitación del contenedor)
3. ✓ Revisa logs de `notification_server.py` para mensajes de error BLE

---

## Flujo de Datos

```
Sensores (3 nodos LoPy4)
    ↓ uplink LoRaWAN
TTN
    ↓ webhook
notification_server.py
    ├─→ Orion (FIWARE)
    ├─→ TTN downlink (LoRaWAN → LoPy4)
    └─→ LEDStateManager
         ├─→ Agrega alertas por nodo
         ├─→ Agrega alertas por tipo
         └─→ BLE Client
              ↓
           ESP32
              ├─→ Indicadores 1-3: Estado de nodos
              ├─→ Indicadores 4-5: Alertas agregadas (temp, humedad)
              └─→ Indicador 6: Acceso NFC
```

---

## Ejemplo: Temperatura Alta en múltiples nodos

### Escenario:
```
s1 (Salón):      32°C → Temperatura alta ⚠️
s2 (Dormitorio): 21°C → OK ✓
s3 (Exterior):    5°C → Temperatura baja ⚠️
```

### Resultado de LEDs:

**Indicadores de Nodo:**
```
Indicador 1 (s1):  🔴 ROJO     (hay alerta de temperatura)
Indicador 2 (s2):  🟢 VERDE    (todo OK)
Indicador 3 (s3):  🔴 ROJO     (hay alerta de temperatura baja)
```

**Indicadores de Alertas Tipo:**
```
Indicador 4 (Temp):    🟡 AMARILLO  (2 nodos con alerta de temperatura)
Indicador 5 (Humedad): 🔵 AZUL      (OK en todos)
```

### Proceso Detallado:

1. s1 mide 32°C → uplink LoRaWAN → TTN → webhook
2. `notification_server.py` recibe uplink
3. `r_temp_alta()` detecta t > 28
4. `_led_manager.add_alert("Sensor:s1", "temp")`
5. `LEDStateManager` recalcula estado:
   - `node_alerts["Sensor:s1"]` = {"temp"}
   - `type_alerts["temp"]` = {"Sensor:s1", "Sensor:s3"}
6. Envía comandos BLE automáticamente:
   - Indicador 1 → Rojo (nodo s1 tiene alertas)
   - Indicador 4 → Amarillo (2 nodos con temp)

---

## Mantenimiento

### Inicializar LEDs al arrancar
Los LEDs se inicializan en `setup()`: indicadores 1-5 en **normal (verde/azul)**, indicador 6 (NFC) **apagado**:
```cpp
for (int i = 0; i < 6; i++) {
    bool initNormal = (i < 5);  // Indicador 6 (NFC) arranca apagado
    _setLEDState(i, false, initNormal);
}
```

### Test de LEDs
Envía comandos manuales desde una terminal BLE:
```bash
# Linux con bleak:
python3 -c "
import asyncio
from bleak import BleakScanner, BleakClient

async def test():
    scanner = BleakScanner()
    devices = await scanner.discover()
    for d in devices:
        if 'NFC' in (d.name or ''):
            print(f'Encontrado: {d.address}')
            async with BleakClient(d.address) as client:
                # Indicador 1 rojo
                await client.write_gatt_char(
                    'b1d2e3f4-5a6b-7c8d-9e0f-a1b2c3d4e5f6',
                    bytes([0x01, 0x01, 0x00])
                )
            break

asyncio.run(test())
"
```

### Simular alertas sin hardware real

Llama al endpoint `/iot/ul` con payloads TTN falsos para disparar el pipeline completo (reglas, downlinks TTN, comandos BLE):

```bash
# Temperatura alta en Salón → Indicador 1 rojo + Indicador 4 naranja
curl -X POST http://localhost:5000/iot/ul \
  -H "Content-Type: application/json" \
  -d '{"end_device_ids": {"device_id": "lopy4-salon"}, "uplink_message": {"decoded_payload": {"temperature": 35, "humidity": 50}}}'

# Temperatura alta también en Dormitorio → Indicador 4 amarillo (crítico)
curl -X POST http://localhost:5000/iot/ul \
  -H "Content-Type: application/json" \
  -d '{"end_device_ids": {"device_id": "lopy4-dormitorio"}, "uplink_message": {"decoded_payload": {"temperature": 35, "humidity": 50}}}'

# Humedad alta en Exterior → Indicador 3 rojo + Indicador 5 naranja
curl -X POST http://localhost:5000/iot/ul \
  -H "Content-Type: application/json" \
  -d '{"end_device_ids": {"device_id": "lopy4-exterior"}, "uplink_message": {"decoded_payload": {"temperature": 20, "humidity": 90}}}'

# Volver a estado normal en Salón
curl -X POST http://localhost:5000/iot/ul \
  -H "Content-Type: application/json" \
  -d '{"end_device_ids": {"device_id": "lopy4-salon"}, "uplink_message": {"decoded_payload": {"temperature": 20, "humidity": 50}}}'
```

---

## Referencias

- [BLE Spec](https://www.bluetooth.com/specifications/)
- [ESP32 Arduino](https://github.com/espressif/arduino-esp32)
- [Bleak Documentation](https://bleak.readthedocs.io/)
- [PN532 Library](https://github.com/Seeed-Studio/PN532)
