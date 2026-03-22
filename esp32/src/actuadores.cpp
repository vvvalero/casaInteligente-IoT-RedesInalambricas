// ============================================================
// actuadores.cpp — Control de relés y procesado de downlinks
// ============================================================
// Protocolo de downlink (FPort = 1, 2 bytes):
//   Byte 0: ID de comando
//     0x01 = luz ON/OFF
//     0x02 = AC ON/OFF
//     0x03 = alarma ON/OFF
//   Byte 1: valor (0 = OFF / apagar, 1 = ON / activar)
// ============================================================

#include "actuadores.h"
#include "config.h"

// Estado actual de los actuadores
static bool _luz    = false;
static bool _ac     = false;
static bool _alarma = false;

// ---- IDs de comandos downlink ----
#define CMD_LUZ    0x01
#define CMD_AC     0x02
#define CMD_ALARMA 0x03

void actuadores_init() {
    pinMode(RELAY_LUZ,    OUTPUT);
    pinMode(RELAY_AC,     OUTPUT);
    pinMode(RELAY_ALARMA, OUTPUT);

    // Estado inicial: todo apagado
    digitalWrite(RELAY_LUZ,    LOW);
    digitalWrite(RELAY_AC,     LOW);
    digitalWrite(RELAY_ALARMA, LOW);

    Serial.println("[Actuadores] Iniciados (luz=OFF, AC=OFF, alarma=OFF)");
}

void actuador_luz(bool encendido) {
    _luz = encendido;
    digitalWrite(RELAY_LUZ, encendido ? HIGH : LOW);
    Serial.printf("[Actuadores] Luz: %s\n", encendido ? "ON" : "OFF");
}

void actuador_ac(bool encendido) {
    _ac = encendido;
    digitalWrite(RELAY_AC, encendido ? HIGH : LOW);
    Serial.printf("[Actuadores] AC: %s\n", encendido ? "ON" : "OFF");
}

void actuador_alarma(bool activada) {
    _alarma = activada;
    digitalWrite(RELAY_ALARMA, activada ? HIGH : LOW);
    Serial.printf("[Actuadores] Alarma: %s\n", activada ? "ACTIVADA" : "DESACTIVADA");
}

void actuadores_procesar_downlink(uint8_t puerto,
                                  const uint8_t* datos,
                                  uint8_t longitud) {
    // Solo procesamos el puerto 1 (comandos de actuadores)
    if (puerto != 1) {
        Serial.printf("[Actuadores] Downlink ignorado (puerto %d)\n", puerto);
        return;
    }
    if (longitud < 2) {
        Serial.println("[Actuadores] Downlink demasiado corto (mínimo 2 bytes)");
        return;
    }

    uint8_t cmd   = datos[0];
    uint8_t valor = datos[1];

    Serial.printf("[Actuadores] Downlink recibido: cmd=0x%02X valor=%d\n", cmd, valor);

    switch (cmd) {
        case CMD_LUZ:
            actuador_luz(valor != 0);
            break;
        case CMD_AC:
            actuador_ac(valor != 0);
            break;
        case CMD_ALARMA:
            actuador_alarma(valor != 0);
            break;
        default:
            Serial.printf("[Actuadores] Comando desconocido: 0x%02X\n", cmd);
            break;
    }
}

bool actuador_estado_luz()    { return _luz; }
bool actuador_estado_ac()     { return _ac; }
bool actuador_estado_alarma() { return _alarma; }
