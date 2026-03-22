#ifndef CAYENNE_LPP_H
#define CAYENNE_LPP_H

// ============================================================
// cayenne_lpp.h — Codificador/Decodificador Cayenne LPP
// ============================================================
// Cayenne Low Power Payload — formato compacto para IoT
//
// Estructura de cada campo:
//   [canal: 1 byte] [tipo: 1 byte] [valor: N bytes, big-endian]
//
// Tipos implementados (según especificación myDevices):
//   0x67  Digital Input     1 byte    sin escala
//   0x65  Luminosidad       2 bytes   1 lux/bit
//   0x66  Presence          1 byte    sin escala (0/1)
//   0x67  Temperature       2 bytes   0.1 °C/bit (signed)
//   0x68  Humidity          1 byte    0.5 %RH/bit (unsigned)
//   0x73  Barometric Press. 2 bytes   0.1 hPa/bit (unsigned)
// ============================================================

#include <Arduino.h>
#include <stdint.h>

// Códigos de tipo Cayenne LPP
#define LPP_DIGITAL_INPUT       0x00   // 1 byte
#define LPP_DIGITAL_OUTPUT      0x01   // 1 byte
#define LPP_ANALOG_INPUT        0x02   // 2 bytes, ×100
#define LPP_LUMINOSITY          0x65   // 2 bytes, 1 lux/bit
#define LPP_PRESENCE            0x66   // 1 byte, 0/1
#define LPP_TEMPERATURE         0x67   // 2 bytes, 0.1°C/bit, signed
#define LPP_HUMIDITY            0x68   // 1 byte, 0.5%/bit, unsigned
#define LPP_BAROMETRIC_PRESSURE 0x73   // 2 bytes, 0.1hPa/bit, unsigned

// Tamaños en bytes de cada tipo (valor, sin canal ni tipo)
#define LPP_SIZE_DIGITAL_INPUT        1
#define LPP_SIZE_LUMINOSITY           2
#define LPP_SIZE_PRESENCE             1
#define LPP_SIZE_TEMPERATURE          2
#define LPP_SIZE_HUMIDITY             1
#define LPP_SIZE_BAROMETRIC_PRESSURE  2

// Overhead por campo: 1 byte canal + 1 byte tipo
#define LPP_FIELD_OVERHEAD  2

// Tamaño máximo del buffer (ajustable)
#define LPP_MAX_SIZE  51

class CayenneLPP {
public:
    // Constructor: inicializa con tamaño máximo del buffer
    CayenneLPP(uint8_t maxSize = LPP_MAX_SIZE);
    ~CayenneLPP();

    // Reinicia el buffer (no libera memoria)
    void reset();

    // Retorna el número de bytes escritos
    uint8_t getSize() const;

    // Retorna puntero al buffer (para envío por LoRaWAN)
    const uint8_t* getBuffer() const;

    // Copia el buffer a un array externo, retorna tamaño
    uint8_t copy(uint8_t* dst) const;

    // ---- Métodos de codificación ----
    // Retornan true si hay espacio suficiente, false si overflow

    // Temperatura: resolución 0.1°C, rango -3276.8 a +3276.7°C
    bool addTemperature(uint8_t channel, float celsius);

    // Humedad: resolución 0.5%, rango 0 a 127.5%
    bool addHumidity(uint8_t channel, float rh);

    // Presión barométrica: resolución 0.1hPa, rango 0 a 6553.5hPa
    bool addBarometricPressure(uint8_t channel, float hpa);

    // Luminosidad: resolución 1 lux, rango 0 a 65535 lux
    bool addLuminosity(uint8_t channel, uint16_t lux);

    // Presencia: 0 = ausente, 1 = detectado
    bool addPresence(uint8_t channel, uint8_t value);

    // Entrada digital genérica: 0 o 1
    bool addDigitalInput(uint8_t channel, uint8_t value);

    // ---- Debug ----
    void printHex(Stream& serial) const;

private:
    uint8_t* _buffer;
    uint8_t  _maxSize;
    uint8_t  _cursor;   // siguiente posición libre

    bool _hasSpace(uint8_t needed) const;
};

#endif // CAYENNE_LPP_H
