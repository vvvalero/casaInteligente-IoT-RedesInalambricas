// nfc_ble_broadcaster.ino — ESP32 como puente NFC → BLE Advertising (cola)
// ============================================================
// Rol en la arquitectura:
//   1. Lee UIDs de tarjetas ISO14443A con un PN532 por I²C
//   2. Los acumula en una cola FIFO de hasta MAX_QUEUE entradas
//   3. Publica toda la cola en el Manufacturer Specific Data BLE
//   4. Cada entrada expira individualmente tras UID_TTL_MS ms
//
// El LoPy4 del dormitorio lee la cola completa en un solo escaneo
// y envía un uplink LoRaWAN por cada UID pendiente.
//
// Formato Manufacturer Specific Data (tipo 0xFF en advertising):
//   [0x34][0x12]       ← Company ID 0x1234 (little-endian, personalizado)
//   [0x4E][0x46][0x43] ← Cabecera ASCII "NFC"
//   [count]            ← Número de UIDs en cola (0 = vacío)
//   [len1][uid1...]    ← Primer UID con prefijo de longitud
//   [len2][uid2...]    ← Segundo UID (si existe)
//   ...
//
// Presupuesto de bytes (payload BLE máx. 31):
//   Flags AD:    3 bytes  (02 01 06)
//   Mfr AD hdr:  2 bytes  (length + 0xFF)
//   Company ID:  2 bytes
//   "NFC":       3 bytes
//   count:       1 byte
//   ──────────────────────────────────────
//   Disponible para UIDs: 20 bytes
//   UIDs de 4 bytes: hasta 4  (5 bytes c/u con prefijo longitud)
//   UIDs de 7 bytes: hasta 2  (8 bytes c/u con prefijo longitud)
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
// ============================================================

#include <Wire.h>
#include <PN532_I2C.h>
#include <PN532.h>
#include <BLEDevice.h>
#include <BLEAdvertising.h>

// --- Configuración de hardware ---
#define NFC_RST_PIN 32

// --- Protocolo BLE-NFC ---
#define COMPANY_ID_LOW  0x34
#define COMPANY_ID_HIGH 0x12

// Entradas máximas en la cola (limitado por los 20 bytes libres del payload)
#define MAX_QUEUE 4

// Tiempo que un UID permanece en la cola tras su última lectura (ms).
// Debe ser mayor que TX_INTERVAL del LoPy4 (60 s).
#define UID_TTL_MS 90000

// ============================================================
// COLA DE UIDs
// ============================================================
struct UIDEntry {
    uint8_t uid[7];
    uint8_t len;
    unsigned long ts;
    bool active;
};

PN532_I2C pn532_i2c(Wire);
PN532 nfc(pn532_i2c);

BLEAdvertising* pAdvertising = nullptr;
UIDEntry uidQueue[MAX_QUEUE];

// ============================================================
// GESTIÓN DE COLA
// ============================================================

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

// Añade un UID a la cola. Si ya existe refresca su TTL.
// Si la cola está llena sustituye la entrada más antigua.
// Devuelve true si el anuncio debe actualizarse.
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
        // Cola llena: reemplaza la más antigua
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

// Expira entradas caducadas. Devuelve true si algo cambió.
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
    Serial.println("\n=== ESP32 NFC-BLE Broadcaster (cola) ===");

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
    pAdvertising = BLEDevice::getAdvertising();
    pAdvertising->setScanResponse(false);

    _initQueue();
    _buildAndStartAdvertising();

    Serial.print("[BLE] Anunciando. MAC: ");
    Serial.println(BLEDevice::getAddress().toString().c_str());
    Serial.println("[SYS] Listo — esperando tarjetas NFC...\n");
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
