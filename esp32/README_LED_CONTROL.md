# Control de LEDs simples vía BLE — ESP32 NFC-BLE Broadcaster (7 indicadores con LEDs simples)

## Descripción General

El ESP32 controla **7 indicadores de estado**, cada uno compuesto por **2 LEDs simples** (rojo y verde):
- **Indicadores 1-3**: Estado de cada nodo (verde=OK, rojo=alerta)
- **Indicadores 4-6**: Alertas por tipo agregadas (temperatura, presión, humedad)
- **Indicador 7**: Estado general del sistema

Los LEDs se actualizan automáticamente con lógica inteligente de agregación.

### Mapeo de Indicadores (7 totales, 14 LEDs)

| Indicador | GPIO R | GPIO G | Propósito |
|-----------|--------|--------|-----------|
| **1** | 25 | 26 | **Nodo s1 (Salón)** |
| **2** | 12 | 13 | **Nodo s2 (Dormitorio)** |
| **3** | 15 | 2 | **Nodo s3 (Exterior)** |
| **4** | 5 | 18 | **Temperatura (agregado)** |
| **5** | 19 | 23 | **Presión (agregado)** |
| **6** | 24 | 9 | **Humedad (agregado)** |
| **7** | 10 | 11 | **Sistema general** |

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
Si s3 tiene presión baja:        Indicador 3 = Rojo
```

### Indicadores 4-6 — Alertas por Tipo (Agregadas de todos los nodos)

Cada indicador muestra si hay ese tipo de alerta en algún nodo:

```
Indicador 4: Temperatura (temp alta o baja en cualquier nodo)
Indicador 5: Presión (presión baja en cualquier nodo)
Indicador 6: Humedad (humedad alta en cualquier nodo)
```

**Estados:**
- 🟢 **Verde** — OK en todos los nodos (solo LED verde encendido)
- 🔴 **Rojo** — Alerta en 1 nodo (solo LED rojo encendido)
- 🟡 **Amarillo** — Alerta en 2+ nodos (ambos LEDs encendidos = crítico)

**Ejemplo:**
```
Si s1 tiene temp alta y s2 tiene temp baja:
  Indicador 4 = Amarillo (crítico: 2 nodos con alerta de temperatura)

Si solo s3 tiene presión baja:
  Indicador 5 = Rojo (1 nodo con alerta)

Si todos OK:
  Indicador 5 = Verde
```

### Indicador 7 — Sistema General

Estado crítico del sistema:

**Estados:**
- 🟢 **Verde** — Todo OK (solo LED verde)
- 🟡 **Amarillo** — Hay alertas (warning: ambos LEDs)
- 🔴 **Rojo** — Crítico (solo LED rojo: NFC denegado o vibración)

**Ejemplo:**
```
Sistema normal:                    Indicador 7 = Verde
Hay varios warnings activos:        Indicador 7 = Amarillo
Acceso NFC denegado detectado:      Indicador 7 = Rojo
```

---

## Protocolo BLE

### Servicio BLE
- **UUID**: `a6e3ed8d-6a2f-4a8b-9b8c-1c9f8e7d6c5b`

### Característica de Comando LED
- **UUID**: `b1d2e3f4-5a6b-7c8d-9e0f-a1b2c3d4e5f6`
- **Tipo**: Write
- **Formato**: 3 bytes: `[led_id][red_on][green_on]`

### Ejemplo de Comandos

```
Indicador 1 (s1) rojo:           [0x01, 0x01, 0x00]
Indicador 2 (s2) verde:          [0x02, 0x00, 0x01]
Indicador 3 (s3) amarillo:       [0x03, 0x01, 0x01]
Indicador 4 (Temp) rojo:         [0x04, 0x01, 0x00]
Indicador 5 (Presión) verde:     [0x05, 0x00, 0x01]
Indicador 6 (Humedad) amarillo:  [0x06, 0x01, 0x01]
Indicador 7 (Sistema) apagado:   [0x07, 0x00, 0x00]
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
- 1 LED rojo (ánodo → GPIO, cátodo → GND con resistencia)
- 1 LED verde (ánodo → GPIO, cátodo → GND con resistencia)
- Resistencia por LED: ~220Ω (para ~20mA a 2V)

**Pines usados (14 total, 2 por indicador):**
```
Indicador 1 (s1):        GPIO 25 (R), 26 (G)
Indicador 2 (s2):        GPIO 12 (R), 13 (G)
Indicador 3 (s3):        GPIO 15 (R), 2 (G)
Indicador 4 (Temp):      GPIO 5 (R), 18 (G)
Indicador 5 (Presión):   GPIO 19 (R), 23 (G)
Indicador 6 (Humedad):   GPIO 24 (R), 9 (G)
Indicador 7 (Sistema):   GPIO 10 (R), 11 (G)
```

**Reservados (no disponibles):**
- GPIO 21, 22: I²C para PN532
- GPIO 32: Reset del PN532
- GPIO 34-39: Solo entrada analógica (sin soporte digital)

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
_ble_client = BLELEDClient(device_name="ESP32-NFC-Door")  # ← Cambiar aquí
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
    ├─→ TTN downlink (LoRaWAN)
    └─→ LEDStateManager
         ├─→ Agrega alertas por nodo
         ├─→ Agrega alertas por tipo
         ├─→ Calcula estado crítico
         └─→ BLE Client
              ↓
           ESP32
              ├─→ Indicadores 1-3: Estado de nodos
              ├─→ Indicadores 4-6: Alertas agregadas
              └─→ Indicador 7: Sistema general
```

---

## Ejemplo: Temperatura Alta en múltiples nodos

### Escenario:
```
s1 (Salón):     32°C → Temperatura alta ⚠️
s2 (Dormitorio): 21°C → OK ✓
s3 (Exterior):   5°C → Temperatura baja ⚠️
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
Indicador 4 (Temp):    🟡 AMARILLO  (2+ nodos con alerta de temperatura)
Indicador 5 (Presión): 🟢 VERDE     (OK en todos)
Indicador 6 (Humedad): 🟢 VERDE     (OK en todos)
```

**Indicador Sistema:**
```
Indicador 7:  🟡 AMARILLO  (hay warnings activos)
```

### Proceso Detallado:

1. s1 mide 32°C → uplink LoRaWAN → TTN → webhook
2. `notification_server.py` recibe uplink
3. `r_temp_alta()` detecta t > 28
4. `_led_manager.add_alert("Sensor:s1", "temp")`
5. LEDStateManager recalcula estado:
   - `node_alerts["Sensor:s1"]` = {"temp"}
   - `type_alerts["temp"]` = {"Sensor:s1", "Sensor:s3"}
6. Envía comandos BLE automáticamente:
   - Indicador 1 → Rojo (nodo s1 tiene alertas)
   - Indicador 4 → Amarillo (2 nodos con temp)
7. Usuario ve:
   - Alerta en webapp (FIWARE Orion)
   - LEDs rojos/amarillos en hardware mostrando qué está mal
   - Puede identificar rápidamente s1 y s3 tienen problemas de temperatura

---

## Mantenimiento

### Inicializar LEDs al arrancar
Los LEDs se inicializan en **verde** en `setup()`:
```cpp
for (int i = 0; i < 7; i++) {
    _setLEDState(i, false, true);  // Verde (OK)
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

---

## Referencias

- [BLE Spec](https://www.bluetooth.com/specifications/)
- [ESP32 Arduino](https://github.com/espressif/arduino-esp32)
- [Bleak Documentation](https://bleak.readthedocs.io/)
- [PN532 Library](https://github.com/Seeed-Studio/PN532)
