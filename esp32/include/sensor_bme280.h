#ifndef SENSOR_BME280_H
#define SENSOR_BME280_H

// ============================================================
// sensor_bme280.h — Interfaz del módulo BME280
// ============================================================

#include <Arduino.h>

struct DatosBME280 {
    float temperatura;   // °C
    float humedad;       // %RH
    float presion;       // hPa
    bool  validos;       // true si la lectura fue correcta
};

bool    bme280_init();
DatosBME280 bme280_leer();

#endif
