// ============================================================
// sensor_bme280.cpp — Lectura del sensor Bosch BME280
// ============================================================
// Librería requerida: "Adafruit BME280 Library" (instalar en
// Arduino IDE → Gestor de librerías → buscar "Adafruit BME280")
// Dependencia automática: "Adafruit Unified Sensor"
//
// Comunicación: I²C a 400 kHz
//   SDA → GPIO 21 (ESP32 por defecto)
//   SCL → GPIO 22 (ESP32 por defecto)
//   VCC → 3.3 V
//   GND → GND
//   CSB → 3.3 V (fuerza modo I²C)
//   SDO → GND (dirección 0x76) o 3.3V (dirección 0x77)
// ============================================================

#include "sensor_bme280.h"
#include "config.h"
#include <Wire.h>
#include <Adafruit_BME280.h>

static Adafruit_BME280 bme;
static bool _inicializado = false;

// ------------------------------------------------------------
// bme280_init()
// Inicializa el bus I²C y el sensor.
// Retorna true si el sensor responde correctamente.
// ------------------------------------------------------------
bool bme280_init() {
    Wire.begin(I2C_SDA, I2C_SCL);

    if (!bme.begin(BME280_ADDR)) {
        Serial.println("[BME280] ERROR: sensor no encontrado en 0x"
                       + String(BME280_ADDR, HEX));
        Serial.println("[BME280] Comprueba el cableado SDA/SCL y la dirección I2C");
        _inicializado = false;
        return false;
    }

    // Configuración para uso en interiores (modo normal, oversampling x1)
    // Modos disponibles: weather monitoring / humidity sensing / indoor nav / gaming
    // Para esta aplicación: lectura cada 15 min → weather monitoring mode
    bme.setSampling(
        Adafruit_BME280::MODE_FORCED,       // Lectura única bajo demanda
        Adafruit_BME280::SAMPLING_X1,       // Temperatura oversampling ×1
        Adafruit_BME280::SAMPLING_X1,       // Presión oversampling ×1
        Adafruit_BME280::SAMPLING_X1,       // Humedad oversampling ×1
        Adafruit_BME280::FILTER_OFF,        // Sin filtro IIR (lectura instantánea)
        Adafruit_BME280::STANDBY_MS_1000    // No aplica en MODE_FORCED
    );

    _inicializado = true;
    Serial.println("[BME280] Sensor inicializado correctamente (0x"
                   + String(BME280_ADDR, HEX) + ")");
    return true;
}

// ------------------------------------------------------------
// bme280_leer()
// Fuerza una medición y retorna los valores calibrados.
// En MODE_FORCED el sensor mide, actualiza registros y vuelve
// a sleep automáticamente → ideal para batería.
// ------------------------------------------------------------
DatosBME280 bme280_leer() {
    DatosBME280 datos = { 0.0f, 0.0f, 0.0f, false };

    if (!_inicializado) {
        Serial.println("[BME280] Sensor no inicializado");
        return datos;
    }

    // Forzar medición (el sensor vuelve a sleep tras completarla)
    bme.takeForcedMeasurement();

    float temp = bme.readTemperature();   // °C
    float hum  = bme.readHumidity();     // %RH
    float pres = bme.readPressure() / 100.0F;  // Pa → hPa

    // Validar rango de valores
    if (isnan(temp) || isnan(hum) || isnan(pres)) {
        Serial.println("[BME280] ERROR: lectura inválida (NaN)");
        return datos;
    }
    if (temp < -40.0f || temp > 85.0f) {
        Serial.println("[BME280] AVISO: temperatura fuera de rango: " + String(temp));
    }
    if (hum < 0.0f || hum > 100.0f) {
        Serial.println("[BME280] AVISO: humedad fuera de rango: " + String(hum));
    }

    datos.temperatura = temp;
    datos.humedad     = hum;
    datos.presion     = pres;
    datos.validos     = true;

    Serial.printf("[BME280] T=%.1f°C  H=%.1f%%  P=%.1f hPa\n",
                  datos.temperatura, datos.humedad, datos.presion);
    return datos;
}
