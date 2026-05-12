// nfc_ble_broadcaster.ino — ESP32 como puente NFC → BLE + Control de LEDs simples
// ============================================================
// Rol en la arquitectura:
//   1. Lee UIDs de tarjetas ISO14443A con un PN532 por I²C
//   2. Los acumula en una cola FIFO de hasta MAX_QUEUE entradas
//   3. Publica toda la cola en BLE Advertising (Manufacturer Specific Data)
//   4. Expone servicio BLE para recibir comandos de control de LEDs
//   5. Controla 8 indicadores con LEDs simples (on/off): 16 GPIO totales
//
// El LoPy4 del dormitorio lee la cola NFC vía BLE escaneo.
// El notification_server.py envía comandos de LED vía BLE client.
//
// Formato Manufacturer Specific Data (tipo 0xFF en advertising):
//   [0x34][0x12]       ← Company ID 0x1234 (little-endian, personalizado)
//   [0x4E][0x46][0x43] ← Cabecera ASCII "NFC"
//   [count]            ← Número de UIDs en cola (0 = vacío)
//   [len1][uid1...]    ← Primer UID con prefijo de longitud
//   [len2][uid2...]    ← Segundo UID (si existe)
//   ...
//
// Comando BLE LED (característica escribible):
//   [led_id][red_on][green_on]
//   led_id: 1-8 (qué indicador)
//   red_on: 0 o 1 (encender LED rojo)
//   green_on: 0 o 1 (encender LED verde)
//   Ejemplo: [1, 0, 1] = indicador 1 verde (OK)
//            [1, 1, 0] = indicador 1 rojo (alerta)
//            [1, 1, 1] = indicador 1 amarillo (crítico, ambos encendidos)
//
// Librerías necesarias (Library Manager de Arduino IDE):
//   - "PN532" de Elechouse (elechouse/PN532)
//   - "ESP32 BLE Arduino" (ya incluida en el paquete esp32 de Espressif)
//
// Conexión PN532 por I²C (pines por defecto del ESP32):
//   PN532 SDA → GPIO 21
//   PN532 SCL → GPIO 22
//   PN532 VCC → 3.3 V
//   PN532 GND → GND
//   PN532 RST → GPIO 32  (opcional, recomendado)
//   PN532 DIP: SW1=OFF, SW2=ON  (modo I²C)
//
// Pines LED simples — agrupados por tipo, cada par en pines adyacentes del ESP32:
//
//   NODOS (columna derecha del ESP32 — bloque D13,D12,D14,D27,D26,D25):
//   Indicador 1 (Salón):       R=GPIO 25, G=GPIO 26
//   Indicador 2 (Dormitorio):  R=GPIO 12, G=GPIO 13
//   Indicador 3 (Exterior):    R=GPIO 14, G=GPIO 27
//
//   SENSORES (columna izquierda, posiciones 1-4: D15,D2,D4,D16):
//   Indicador 4 (Temperatura): N=GPIO 15, A=GPIO 2
//   Indicador 5 (Humedad):     N=GPIO 4,  A=GPIO 16
//
//   SISTEMA (columna izquierda, posiciones 7-8: D18,D19):
//   Indicador 6 (Acceso NFC):  R=GPIO 18, G=GPIO 19
// ============================================================

#include <Wire.h>
#include <PN532_I2C.h>
#include <PN532.h>
#include <BLEDevice.h>
#include <BLEServer.h>
#include <BLEUtils.h>
#include <BLE2902.h>

// --- Configuración de hardware ---
#define NFC_RST_PIN 32

// --- Protocolo BLE-NFC ---
#define COMPANY_ID_LOW  0x34
#define COMPANY_ID_HIGH 0x12

// Service y Characteristic UUIDs para control de LEDs
#define LED_SERVICE_UUID        "a6e3ed8d-6a2f-4a8b-9b8c-1c9f8e7d6c5b"
#define LED_COMMAND_CHAR_UUID   "b1d2e3f4-5a6b-7c8d-9e0f-a1b2c3d4e5f6"

// Entradas máximas en la cola
#define MAX_QUEUE 4

// Tiempo que un UID permanece en la cola
#define UID_TTL_MS 35000

// --- Pines de LEDs (pin_a=alerta, pin_b=normal) ---
// Indicadores 1-3 y 7-8: pin_a=ROJO,   pin_b=VERDE
// Indicadores 4-6:        pin_a=NARANJA, pin_b=AZUL
struct LEDPins {
    uint8_t pin_a, pin_b;
};

const LEDPins ledPins[6] = {
    {25, 26},   // Indicador 1: Salón       R/V  — col. derecha
    {12, 13},   // Indicador 2: Dormitorio  R/V  — col. derecha
    {14, 27},   // Indicador 3: Exterior    R/V  — col. derecha
    {15,  2},   // Indicador 4: Temperatura N/A  — col. izq. pos.1-2
    { 4, 16},   // Indicador 5: Humedad     N/A  — col. izq. pos.3-4
    {18, 19},   // Indicador 6: Acceso NFC  R/V  — col. izq. pos.7-8
};

// Nombres de color por indicador [pin_a, pin_b]
static const char* COLOR_A[6] = {
    "ROJO", "ROJO", "ROJO", "NARANJA", "NARANJA", "ROJO"
};
static const char* COLOR_B[6] = {
    "VERDE", "VERDE", "VERDE", "AZUL", "AZUL", "VERDE"
};

// ============================================================
// CONTROL DE LEDs
// ============================================================
struct LEDState {
    bool a;  // pin_a: alerta (rojo / naranja según indicador)
    bool b;  // pin_b: normal (verde / azul según indicador)
};

LEDState ledStates[6] = {
    {false, true},   // Indicador 1: Salón       — normal (verde)
    {false, true},   // Indicador 2: Dormitorio  — normal (verde)
    {false, true},   // Indicador 3: Exterior    — normal (verde)
    {false, true},   // Indicador 4: Temperatura — normal (azul)
    {false, true},   // Indicador 5: Humedad     — normal (azul)
    {false, false}   // Indicador 6: NFC         — apagado (sin actividad)
};

// Auto-apagado del indicador NFC (índice 5)
// Verde (acceso concedido): 1500 ms — el usuario ya está pasando
// Rojo  (denegado/desconocido): 2000 ms — necesita registrar el rechazo
static unsigned long nfcLedOffAt = 0;  // millis() en que apagar; 0 = inactivo

static void _setLEDState(int ledIndex, bool a, bool b) {
    if (ledIndex < 0 || ledIndex >= 6) return;

    ledStates[ledIndex].a = a;
    ledStates[ledIndex].b = b;

    digitalWrite(ledPins[ledIndex].pin_a, a ? HIGH : LOW);
    digitalWrite(ledPins[ledIndex].pin_b, b ? HIGH : LOW);

    Serial.print("[LED] Indicador ");
    Serial.print(ledIndex + 1);
    Serial.print(" → ");
    if (a && b) {
        Serial.print(COLOR_A[ledIndex]); Serial.print("+"); Serial.print(COLOR_B[ledIndex]);
        Serial.println(" (crítico)");
    } else if (a) {
        Serial.print(COLOR_A[ledIndex]);
        Serial.println(" (alerta)");
    } else if (b) {
        Serial.print(COLOR_B[ledIndex]);
        Serial.println(" (OK)");
    } else {
        Serial.println("APAGADO");
    }
}

// ============================================================
// BLE CALLBACKS
// ============================================================
class LEDCommandCallback : public BLECharacteristicCallbacks {
    void onWrite(BLECharacteristic* pCharacteristic) {
        uint8_t* data = pCharacteristic->getData();
        size_t len = pCharacteristic->getLength();
        if (len < 3) return;

        uint8_t ledIndex = data[0] - 1;
        uint8_t redOn = data[1];
        uint8_t greenOn = data[2];

        // Validar que ledIndex esté en rango [0,5]
        if (ledIndex >= 6) {
            Serial.print("[LED] ERROR: Indicador ");
            Serial.print(data[0]);
            Serial.println(" fuera de rango (debe ser 1-6)");
            return;
        }

        _setLEDState(ledIndex, redOn != 0, greenOn != 0);

        // Programar auto-apagado solo para el indicador NFC (índice 5)
        if (ledIndex == 5) {
            bool green = (greenOn != 0);
            unsigned long timeout = green ? 1500UL : 2000UL;
            nfcLedOffAt = millis() + timeout;
        }
    }
};

PN532_I2C pn532_i2c(Wire);
PN532 nfc(pn532_i2c);

BLEAdvertising* pAdvertising = nullptr;
BLEServer* pServer = nullptr;

// ============================================================
// COLA DE UIDs
// ============================================================
struct UIDEntry {
    uint8_t uid[7];
    uint8_t len;
    unsigned long ts;
    bool active;
};

UIDEntry uidQueue[MAX_QUEUE];

static void _initQueue() {
    for (int i = 0; i < MAX_QUEUE; i++) {
        uidQueue[i].active = false;
        uidQueue[i].len    = 0;
        uidQueue[i].ts     = 0;
    }
}

static bool _uidEquals(const uint8_t* a, uint8_t aLen,
                       const uint8_t* b, uint8_t bLen) {
    if (aLen != bLen) return false;
    for (int i = 0; i < aLen; i++) {
        if (a[i] != b[i]) return false;
    }
    return true;
}

static bool _addToQueue(const uint8_t* uid, uint8_t uidLen) {
    // Validar que uidLen no exceda el tamaño del buffer
    if (uidLen > 7) {
        Serial.print("[NFC] ERROR: UID demasiado largo (");
        Serial.print(uidLen);
        Serial.println(" bytes, máx 7)");
        uidLen = 7;  // Truncar a tamaño máximo
    }

    for (int i = 0; i < MAX_QUEUE; i++) {
        if (uidQueue[i].active &&
                _uidEquals(uidQueue[i].uid, uidQueue[i].len, uid, uidLen)) {
            uidQueue[i].ts = millis();
            return false;
        }
    }
    int slot = -1;
    for (int i = 0; i < MAX_QUEUE; i++) {
        if (!uidQueue[i].active) { slot = i; break; }
    }
    if (slot == -1) {
        slot = 0;
        for (int i = 1; i < MAX_QUEUE; i++) {
            if (uidQueue[i].ts < uidQueue[slot].ts) slot = i;
        }
    }
    memcpy(uidQueue[slot].uid, uid, uidLen);
    uidQueue[slot].len    = uidLen;
    uidQueue[slot].ts     = millis();
    uidQueue[slot].active = true;
    return true;
}

static bool _expireQueue() {
    bool changed = false;
    unsigned long now = millis();
    for (int i = 0; i < MAX_QUEUE; i++) {
        if (uidQueue[i].active &&
                ((unsigned long)(now - uidQueue[i].ts) >= UID_TTL_MS)) {
            uidQueue[i].active = false;
            changed = true;
        }
    }
    return changed;
}

static int _queueCount() {
    int n = 0;
    for (int i = 0; i < MAX_QUEUE; i++) {
        if (uidQueue[i].active) n++;
    }
    return n;
}

// ============================================================
// ADVERTISING BLE
// ============================================================

static void _buildAndStartAdvertising() {
    String mfr;
    mfr += (char)COMPANY_ID_LOW;
    mfr += (char)COMPANY_ID_HIGH;
    mfr += 'N'; mfr += 'F'; mfr += 'C';

    int count = _queueCount();
    mfr += (char)count;

    for (int i = 0; i < MAX_QUEUE; i++) {
        if (!uidQueue[i].active) continue;
        mfr += (char)uidQueue[i].len;
        for (int j = 0; j < uidQueue[i].len; j++) {
            mfr += (char)uidQueue[i].uid[j];
        }
    }

    BLEAdvertisementData advData;
    advData.setFlags(0x06);
    advData.setManufacturerData(mfr);

    pAdvertising->stop();
    pAdvertising->setAdvertisementData(advData);
    pAdvertising->start();
}

// ============================================================
// SETUP
// ============================================================
void setup() {
    Serial.begin(115200);
    Serial.println("\n=== ESP32 NFC-BLE Broadcaster + LED Control (simple) ===");

    // --- Init LEDs ---
    for (int i = 0; i < 6; i++) {
        pinMode(ledPins[i].pin_a, OUTPUT);
        pinMode(ledPins[i].pin_b, OUTPUT);
        bool initNormal = (i < 5);  // Indicador 6 (NFC) arranca apagado
        _setLEDState(i, false, initNormal);
    }
    Serial.println("[LED] 6 indicadores LED inicializados");

    // --- Init PN532 ---
    pinMode(NFC_RST_PIN, OUTPUT);
    digitalWrite(NFC_RST_PIN, HIGH);
    delay(10);
    digitalWrite(NFC_RST_PIN, LOW);
    delay(500);
    digitalWrite(NFC_RST_PIN, HIGH);
    delay(100);

    nfc.begin();
    uint32_t versiondata = nfc.getFirmwareVersion();
    if (!versiondata) {
        Serial.println("[NFC] ERROR: PN532 no detectado. Revisa cableado y DIP switches.");
        while (true) { delay(500); }
    }

    Serial.print("[NFC] PN532 v");
    Serial.print((versiondata >> 24) & 0xFF, DEC);
    Serial.print('.');
    Serial.println((versiondata >> 16) & 0xFF, DEC);

    nfc.SAMConfig();

    // --- Init BLE ---
    BLEDevice::init("ESP32-NFC-Door");

    // BLE Server para comandos de LED
    pServer = BLEDevice::createServer();
    BLEService* pService = pServer->createService(LED_SERVICE_UUID);
    BLECharacteristic* pCharacteristic = pService->createCharacteristic(
        LED_COMMAND_CHAR_UUID,
        BLECharacteristic::PROPERTY_WRITE
    );
    pCharacteristic->setAccessPermissions(ESP_GATT_PERM_WRITE);
    pCharacteristic->setCallbacks(new LEDCommandCallback());
    pService->start();

    // BLE Advertising (para cola NFC)
    pAdvertising = BLEDevice::getAdvertising();
    pAdvertising->setScanResponse(false);

    _initQueue();
    _buildAndStartAdvertising();

    // Iniciar advertising para el servidor
    pServer->getAdvertising()->start();

    Serial.print("[BLE] MAC: ");
    Serial.println(BLEDevice::getAddress().toString().c_str());
    Serial.println("[SYS] Listo — esperando tarjetas NFC y comandos BLE...\n");
}

// ============================================================
// LOOP
// ============================================================
void loop() {
    // Auto-apagado del indicador NFC tras el timeout configurado
    if (nfcLedOffAt != 0 && (long)(millis() - nfcLedOffAt) >= 0) {
        nfcLedOffAt = 0;
        _setLEDState(5, false, false);
    }

    // Expirar entradas caducadas y actualizar el anuncio si cambió algo
    if (_expireQueue()) {
        _buildAndStartAdvertising();
        Serial.print("[NFC] TTL expirado — cola: ");
        Serial.println(_queueCount());
    }

    // Intentar leer tarjeta (timeout corto para no bloquear)
    uint8_t uid[7];
    uint8_t uidLength = 0;
    bool detectada = nfc.readPassiveTargetID(
        PN532_MIFARE_ISO14443A, uid, &uidLength, 100);

    if (detectada && uidLength > 0) {
        Serial.print("[NFC] Tarjeta detectada, UID: ");
        for (uint8_t i = 0; i < uidLength; i++) {
            if (uid[i] < 0x10) Serial.print('0');
            Serial.print(uid[i], HEX);
        }

        bool esNuevo = _addToQueue(uid, uidLength);
        if (esNuevo) {
            _buildAndStartAdvertising();
            Serial.print(" — NUEVA entrada. Cola: ");
        } else {
            Serial.print(" — ya en cola (TTL refrescado). Cola: ");
        }
        Serial.println(_queueCount());

        delay(1000);
    }

    delay(50);
}
