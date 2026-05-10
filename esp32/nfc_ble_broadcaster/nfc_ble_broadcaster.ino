// nfc_ble_broadcaster.ino — ESP32 como puente NFC → BLE + Control de LEDs simples
// ============================================================
// Rol en la arquitectura:
//   1. Lee UIDs de tarjetas ISO14443A con un PN532 por I²C
//   2. Los acumula en una cola FIFO de hasta MAX_QUEUE entradas
//   3. Publica toda la cola en BLE Advertising (Manufacturer Specific Data)
//   4. Expone servicio BLE para recibir comandos de control de LEDs
//   5. Controla 7 indicadores con LEDs simples (on/off): 14 GPIO totales
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
//   led_id: 1-7 (qué indicador)
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
// Pines LED simples (2 pines por indicador: rojo y verde):
//   Indicador 1 (Nodo s1):     R=GPIO 25, G=GPIO 26
//   Indicador 2 (Nodo s2):     R=GPIO 12, G=GPIO 13
//   Indicador 3 (Nodo s3):     R=GPIO 15, G=GPIO 2
//   Indicador 4 (Temperatura): R=GPIO 5,  G=GPIO 18
//   Indicador 5 (Presión):     R=GPIO 19, G=GPIO 23
//   Indicador 6 (Humedad):     R=GPIO 24, G=GPIO 9
//   Indicador 7 (Sistema):     R=GPIO 10, G=GPIO 11
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
#define UID_TTL_MS 90000

// --- Pines de LEDs simples (rojo y verde por indicador) ---
struct LEDPins {
    uint8_t red, green;
};

const LEDPins ledPins[7] = {
    {25, 26},   // Indicador 1: Nodo s1 (Salón)
    {12, 13},   // Indicador 2: Nodo s2 (Dormitorio)
    {15, 2},    // Indicador 3: Nodo s3 (Exterior)
    {5, 18},    // Indicador 4: Temperatura (agregado)
    {19, 23},   // Indicador 5: Presión (agregado)
    {24, 9},    // Indicador 6: Humedad (agregado)
    {10, 11}    // Indicador 7: Sistema general
};

// ============================================================
// CONTROL DE LEDs
// ============================================================
struct LEDState {
    bool red;
    bool green;
};

LEDState ledStates[7] = {
    {false, true},   // Indicador 1: Verde (OK)
    {false, true},   // Indicador 2: Verde (OK)
    {false, true},   // Indicador 3: Verde (OK)
    {false, true},   // Indicador 4: Verde (OK)
    {false, true},   // Indicador 5: Verde (OK)
    {false, true},   // Indicador 6: Verde (OK)
    {false, true}    // Indicador 7: Verde (OK)
};

static void _setLEDState(int ledIndex, bool red, bool green) {
    if (ledIndex < 0 || ledIndex >= 7) return;

    ledStates[ledIndex].red = red;
    ledStates[ledIndex].green = green;

    digitalWrite(ledPins[ledIndex].red, red ? HIGH : LOW);
    digitalWrite(ledPins[ledIndex].green, green ? HIGH : LOW);

    Serial.print("[LED] Indicador ");
    Serial.print(ledIndex + 1);
    Serial.print(" → ");
    if (red && green) {
        Serial.println("AMARILLO (crítico)");
    } else if (red) {
        Serial.println("ROJO (alerta)");
    } else if (green) {
        Serial.println("VERDE (OK)");
    } else {
        Serial.println("APAGADO");
    }
}

// ============================================================
// BLE CALLBACKS
// ============================================================
class LEDCommandCallback : public BLECharacteristicCallbacks {
    void onWrite(BLECharacteristic* pCharacteristic) {
        std::string value = pCharacteristic->getValue();
        if (value.length() < 3) return;

        uint8_t ledIndex = (uint8_t)value[0] - 1;
        uint8_t redOn = (uint8_t)value[1];
        uint8_t greenOn = (uint8_t)value[2];

        _setLEDState(ledIndex, redOn != 0, greenOn != 0);
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
    for (int i = 0; i < MAX_QUEUE; i++) {
        if (uidQueue[i].active &&
                (millis() - uidQueue[i].ts >= UID_TTL_MS)) {
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
    for (int i = 0; i < 7; i++) {
        pinMode(ledPins[i].red, OUTPUT);
        pinMode(ledPins[i].green, OUTPUT);
        _setLEDState(i, false, true);  // Verde (OK) inicial
    }
    Serial.println("[LED] 7 indicadores LED inicializados (verde)");

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
    pCharacteristic->setAccessPermissions(ESP_GATT_PERM_READ | ESP_GATT_PERM_WRITE);
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
