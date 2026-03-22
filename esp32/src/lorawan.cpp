// ============================================================
// lorawan.cpp — Implementación LoRaWAN sobre MCCI LMIC
// ============================================================
// IMPORTANTE: antes de compilar, crear el fichero
//   lmic_project_config.h en la carpeta del sketch con:
//
//     #define CFG_eu868 1          // Región Europa 868 MHz
//     #define CFG_sx1276_radio 1   // Chip LoRa SX1276
//     #define LMIC_USE_INTERRUPTS  // Usar interrupciones GPIO
//
// Esto sobreescribe la configuración por defecto de LMIC.
// ============================================================

#include "lorawan.h"
#include "config.h"
#include <lmic.h>
#include <hal/hal.h>
#include <SPI.h>

// ---- Credenciales LoRaWAN (desde config.h) ----
// LMIC requiere los arrays en orden LSB para DevEUI y AppEUI,
// MSB para AppKey. Ver comentarios en config.h.

static const uint8_t PROGMEM _deveui[] = DEVEUI;
static const uint8_t PROGMEM _appeui[] = APPEUI;
static const uint8_t PROGMEM _appkey[] = APPKEY;

// Funciones requeridas por LMIC (no renombrar)
void os_getArtEui(uint8_t* buf) { memcpy_P(buf, _appeui, 8); }
void os_getDevEui(uint8_t* buf) { memcpy_P(buf, _deveui, 8); }
void os_getDevKey(uint8_t* buf) { memcpy_P(buf, _appkey, 16); }

// ---- Configuración de pines del módulo LoRa ----
static const lmic_pinmap lmic_pins = {
    .nss   = LORA_SS,
    .rxtx  = LMIC_UNUSED_PIN,
    .rst   = LORA_RST,
    .dio   = { LORA_DIO0, LORA_DIO1, LORA_DIO2 }
};

// ---- Estado interno ----
static EstadoLoRa     _estado        = EstadoLoRa::DESCONECTADO;
static DownlinkCallback _downlink_cb = nullptr;
static osjob_t        _tx_job;
static bool           _tx_pendiente  = false;
static uint8_t        _tx_buf[51];
static uint8_t        _tx_len        = 0;
static uint8_t        _tx_puerto     = 1;
static bool           _tx_confirmar  = false;
static int            _ultimo_rssi   = 0;
static int            _ultimo_snr    = 0;

// ---- Función interna de envío (llamada por LMIC cuando está listo) ----
static void _do_send(osjob_t* j) {
    if (LMIC.opmode & OP_TXRXPEND) {
        Serial.println("[LoRaWAN] TX pendiente, esperando...");
        return;
    }
    if (_tx_pendiente && _tx_len > 0) {
        LMIC_setTxData2(_tx_puerto, _tx_buf, _tx_len,
                        _tx_confirmar ? 1 : 0);
        Serial.printf("[LoRaWAN] TX encolado (%d bytes, puerto %d, SF%d)\n",
                      _tx_len, _tx_puerto, getSf(LMIC.rps) + 7);
        _tx_pendiente = false;
    }
}

// ---- Callback principal de eventos LMIC ----
void onEvent(ev_t ev) {
    switch (ev) {

        case EV_JOINING:
            Serial.println("[LoRaWAN] Iniciando join OTAA...");
            _estado = EstadoLoRa::UNIENDO;
            break;

        case EV_JOINED:
            Serial.println("[LoRaWAN] ✓ Join OTAA completado");
            // Desactivar ADR para mayor control (opcional)
            // LMIC_setAdrMode(0);
            // Deshabilitar confirmaciones de enlace
            LMIC_setLinkCheckMode(0);
            _estado = EstadoLoRa::CONECTADO;
            break;

        case EV_JOIN_FAILED:
            Serial.println("[LoRaWAN] ✗ Join OTAA fallido");
            _estado = EstadoLoRa::ERROR_JOIN;
            break;

        case EV_REJOIN_FAILED:
            Serial.println("[LoRaWAN] ✗ Rejoin fallido");
            _estado = EstadoLoRa::ERROR_JOIN;
            break;

        case EV_TXCOMPLETE:
            _estado = EstadoLoRa::CONECTADO;
            Serial.print("[LoRaWAN] TX completado");

            // ¿Llegó ACK del servidor? (para TX confirmados)
            if (LMIC.txrxFlags & TXRX_ACK) {
                Serial.print(" [ACK recibido]");
            }

            // ¿Hay datos de downlink?
            if (LMIC.dataLen > 0) {
                Serial.printf(" [Downlink: %d bytes en puerto %d]",
                              LMIC.dataLen, LMIC.frame[LMIC.dataBeg - 1]);
                if (_downlink_cb) {
                    _downlink_cb(
                        &LMIC.frame[LMIC.dataBeg],
                        LMIC.dataLen,
                        LMIC.frame[LMIC.dataBeg - 1]  // FPort
                    );
                }
            }
            Serial.println();
            break;

        case EV_TXSTART:
            _estado = EstadoLoRa::ENVIANDO;
            Serial.println("[LoRaWAN] Transmitiendo...");
            break;

        case EV_LINK_DEAD:
            Serial.println("[LoRaWAN] AVISO: enlace muerto (sin ACK del servidor)");
            break;

        case EV_LINK_ALIVE:
            Serial.println("[LoRaWAN] Enlace recuperado");
            break;

        case EV_LOST_TSYNC:
            Serial.println("[LoRaWAN] Sincronización perdida");
            break;

        default:
            Serial.printf("[LoRaWAN] Evento desconocido: %d\n", (int)ev);
            break;
    }
}

// ---- API pública ----

void lorawan_init() {
    SPI.begin(LORA_SCK, LORA_MISO, LORA_MOSI, LORA_SS);
    os_init();
    LMIC_reset();

    // Configuración específica para EU868
    // Desactivar canales 3-7 (LMIC los activa por defecto pero TTN no los usa)
    for (int ch = 3; ch <= 7; ch++) {
        LMIC_disableChannel(ch);
    }

    // Sub-banda FSB2 para EU868 (TTN usa canales 0-2 + 8)
    LMIC_setClockError(MAX_CLOCK_ERROR * 1 / 100);

    Serial.println("[LoRaWAN] LMIC inicializado (EU868)");
    _estado = EstadoLoRa::DESCONECTADO;
}

void lorawan_join() {
    LMIC_startJoining();
    _estado = EstadoLoRa::UNIENDO;
}

EstadoLoRa lorawan_estado() {
    return _estado;
}

bool lorawan_enviar(const uint8_t* payload, uint8_t len,
                    uint8_t puerto, bool confirmar) {
    if (_estado != EstadoLoRa::CONECTADO) return false;
    if (LMIC.opmode & OP_TXRXPEND) return false;
    if (len > sizeof(_tx_buf)) return false;

    memcpy(_tx_buf, payload, len);
    _tx_len       = len;
    _tx_puerto    = puerto;
    _tx_confirmar = confirmar;
    _tx_pendiente = true;

    os_setCallback(&_tx_job, _do_send);
    return true;
}

void lorawan_set_downlink_cb(DownlinkCallback cb) {
    _downlink_cb = cb;
}

void lorawan_loop() {
    os_runloop_once();
}

bool lorawan_listo() {
    return (_estado == EstadoLoRa::CONECTADO) &&
           !(LMIC.opmode & OP_TXRXPEND) &&
           !_tx_pendiente;
}

int lorawan_rssi() { return _ultimo_rssi; }
int lorawan_snr()  { return _ultimo_snr; }

uint8_t lorawan_sf() {
    return getSf(LMIC.rps) + 7;
}
