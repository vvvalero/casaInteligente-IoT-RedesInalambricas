// nfc_ble_broadcaster.ino — ESP32 como puente NFC → BLE Advertising
// ============================================================
// Rol en la arquitectura:
//   1. Lee el UID de tarjetas ISO14443A con un PN532 por I²C
//   2. Inserta el UID en los datos del anuncio BLE (Manufacturer
//      Specific Data, company ID 0x1234) durante UID_TTL_MS ms
//   3. Cuando no hay tarjeta (o expira el TTL), emite el anuncio
//      vacío (flag 0x00)
//
// El LoPy4 del dormitorio escanea periódicamente buscando la
// dirección MAC de este ESP32 y extrae el UID del payload BLE.
//
// Formato Manufacturer Specific Data (tipo 0xFF en advertising):
//   [0x34][0x12]  ← Company ID 0x1234 (little-endian, personalizado)
//   [0x4E][0x46][0x43]  ← Cabecera ASCII "NFC"
//   [0x00 | 0x01]  ← Flag: 0x00 sin tarjeta | 0x01 tarjeta presente
//   [uid0]...[uidN]  ← Bytes del UID (solo si flag=0x01)
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
// TTL del UID en el anuncio BLE tras leer tarjeta (ms)
#define UID_TTL_MS 5000

// ============================================================
// GLOBALES
// ============================================================
PN532_I2C pn532_i2c(Wire);
PN532 nfc(pn532_i2c);

BLEAdvertising* pAdvertising = nullptr;

unsigned long uidTimestamp = 0;
bool uidActivo = false;

// ============================================================
// HELPERS BLE
// ============================================================

// Construye el string de datos del fabricante y actualiza el anuncio.
// uid=nullptr y uidLen=0 emite el anuncio vacío (sin tarjeta).
static void _actualizarAnuncio(const uint8_t* uid, uint8_t uidLen) {
    std::string mfr;
    mfr += (char)COMPANY_ID_LOW;
    mfr += (char)COMPANY_ID_HIGH;
    mfr += 'N'; mfr += 'F'; mfr += 'C';

    if (uid != nullptr && uidLen > 0) {
        mfr += (char)0x01;
        for (uint8_t i = 0; i < uidLen; i++) {
            mfr += (char)uid[i];
        }
    } else {
        mfr += (char)0x00;
    }

    BLEAdvertisementData advData;
    advData.setFlags(0x06);  // LE General Discoverable + no BR/EDR
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
    Serial.println("\n=== ESP32 NFC-BLE Broadcaster ===");

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
        // Parpadeo de error indefinido para señalizar el fallo sin bloquear el micro
        while (true) { delay(500); }
    }

    Serial.print("[NFC] PN532 v");
    Serial.print((versiondata >> 24) & 0xFF, DEC);
    Serial.print('.');
    Serial.println((versiondata >> 16) & 0xFF, DEC);

    nfc.SAMConfig();  // Modo normal, sin timeout de SAM

    // --- Init BLE ---
    BLEDevice::init("ESP32-NFC-Door");
    pAdvertising = BLEDevice::getAdvertising();
    pAdvertising->setScanResponse(false);

    _actualizarAnuncio(nullptr, 0);

    Serial.print("[BLE] Anunciando. MAC: ");
    Serial.println(BLEDevice::getAddress().toString().c_str());
    Serial.println("[SYS] Listo — esperando tarjetas NFC...\n");
}

// ============================================================
// LOOP
// ============================================================
void loop() {
    // Expirar UID si ha pasado el TTL
    if (uidActivo && (millis() - uidTimestamp >= UID_TTL_MS)) {
        _actualizarAnuncio(nullptr, 0);
        uidActivo = false;
        Serial.println("[NFC] TTL expirado — anuncio limpiado");
    }

    // Intentar leer tarjeta (timeout corto para no bloquear el loop)
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
        Serial.println();

        _actualizarAnuncio(uid, uidLength);
        uidTimestamp = millis();
        uidActivo = true;

        // Pausa para evitar lecturas duplicadas de la misma tarjeta
        delay(1000);
    }

    delay(50);
}
