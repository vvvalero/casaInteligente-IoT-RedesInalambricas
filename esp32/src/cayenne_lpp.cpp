// ============================================================
// cayenne_lpp.cpp — Implementación del codificador Cayenne LPP
// ============================================================

#include "cayenne_lpp.h"
#include <string.h>   // memcpy

// ---- Constructor / Destructor ----

CayenneLPP::CayenneLPP(uint8_t maxSize)
    : _maxSize(maxSize), _cursor(0) {
    _buffer = new uint8_t[maxSize];
    memset(_buffer, 0, maxSize);
}

CayenneLPP::~CayenneLPP() {
    delete[] _buffer;
}

// ---- Gestión del buffer ----

void CayenneLPP::reset() {
    _cursor = 0;
    memset(_buffer, 0, _maxSize);
}

uint8_t CayenneLPP::getSize() const {
    return _cursor;
}

const uint8_t* CayenneLPP::getBuffer() const {
    return _buffer;
}

uint8_t CayenneLPP::copy(uint8_t* dst) const {
    memcpy(dst, _buffer, _cursor);
    return _cursor;
}

bool CayenneLPP::_hasSpace(uint8_t needed) const {
    return (_cursor + needed) <= _maxSize;
}

// ---- Temperatura ----
// Resolución: 0.1 °C → multiplicar por 10 → int16_t big-endian
// Ejemplo: 23.1°C → raw = 231 → 0x00 0xE7
// Ejemplo: -4.5°C → raw = -45 → 0xFF 0xD3

bool CayenneLPP::addTemperature(uint8_t channel, float celsius) {
    uint8_t needed = LPP_FIELD_OVERHEAD + LPP_SIZE_TEMPERATURE;
    if (!_hasSpace(needed)) return false;

    int16_t raw = (int16_t)(celsius * 10.0f);

    _buffer[_cursor++] = channel;
    _buffer[_cursor++] = LPP_TEMPERATURE;
    _buffer[_cursor++] = (uint8_t)(raw >> 8);    // MSB
    _buffer[_cursor++] = (uint8_t)(raw & 0xFF);  // LSB
    return true;
}

// ---- Humedad ----
// Resolución: 0.5 %RH → multiplicar por 2 → uint8_t
// Ejemplo: 55.5% → raw = 111 → 0x6F
// Rango: 0 a 127.5% (uint8_t máx = 255 → 127.5%)

bool CayenneLPP::addHumidity(uint8_t channel, float rh) {
    uint8_t needed = LPP_FIELD_OVERHEAD + LPP_SIZE_HUMIDITY;
    if (!_hasSpace(needed)) return false;

    // Limitar al rango válido antes de convertir
    rh = constrain(rh, 0.0f, 100.0f);
    uint8_t raw = (uint8_t)(rh * 2.0f);

    _buffer[_cursor++] = channel;
    _buffer[_cursor++] = LPP_HUMIDITY;
    _buffer[_cursor++] = raw;
    return true;
}

// ---- Presión Barométrica ----
// Resolución: 0.1 hPa → multiplicar por 10 → uint16_t big-endian
// Ejemplo: 1013.25 hPa → raw = 10132 → 0x27 0x94

bool CayenneLPP::addBarometricPressure(uint8_t channel, float hpa) {
    uint8_t needed = LPP_FIELD_OVERHEAD + LPP_SIZE_BAROMETRIC_PRESSURE;
    if (!_hasSpace(needed)) return false;

    uint16_t raw = (uint16_t)(hpa * 10.0f);

    _buffer[_cursor++] = channel;
    _buffer[_cursor++] = LPP_BAROMETRIC_PRESSURE;
    _buffer[_cursor++] = (uint8_t)(raw >> 8);
    _buffer[_cursor++] = (uint8_t)(raw & 0xFF);
    return true;
}

// ---- Luminosidad ----
// Resolución: 1 lux → uint16_t big-endian
// Ejemplo: 350 lux → 0x01 0x5E

bool CayenneLPP::addLuminosity(uint8_t channel, uint16_t lux) {
    uint8_t needed = LPP_FIELD_OVERHEAD + LPP_SIZE_LUMINOSITY;
    if (!_hasSpace(needed)) return false;

    _buffer[_cursor++] = channel;
    _buffer[_cursor++] = LPP_LUMINOSITY;
    _buffer[_cursor++] = (uint8_t)(lux >> 8);
    _buffer[_cursor++] = (uint8_t)(lux & 0xFF);
    return true;
}

// ---- Presencia ----
// 0 = sin presencia, 1 = presencia detectada

bool CayenneLPP::addPresence(uint8_t channel, uint8_t value) {
    uint8_t needed = LPP_FIELD_OVERHEAD + LPP_SIZE_PRESENCE;
    if (!_hasSpace(needed)) return false;

    _buffer[_cursor++] = channel;
    _buffer[_cursor++] = LPP_PRESENCE;
    _buffer[_cursor++] = value ? 1 : 0;
    return true;
}

// ---- Entrada Digital ----

bool CayenneLPP::addDigitalInput(uint8_t channel, uint8_t value) {
    uint8_t needed = LPP_FIELD_OVERHEAD + LPP_SIZE_DIGITAL_INPUT;
    if (!_hasSpace(needed)) return false;

    _buffer[_cursor++] = channel;
    _buffer[_cursor++] = LPP_DIGITAL_INPUT;
    _buffer[_cursor++] = value ? 1 : 0;
    return true;
}

// ---- Debug: imprime el buffer en hexadecimal ----

void CayenneLPP::printHex(Stream& serial) const {
    serial.print("[LPP] Buffer (");
    serial.print(_cursor);
    serial.print(" bytes): ");
    for (uint8_t i = 0; i < _cursor; i++) {
        if (_buffer[i] < 0x10) serial.print('0');
        serial.print(_buffer[i], HEX);
        serial.print(' ');
    }
    serial.println();
}
