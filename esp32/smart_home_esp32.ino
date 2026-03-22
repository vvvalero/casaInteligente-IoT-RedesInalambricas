// ============================================================
// smart_home_esp32.ino — Sketch principal Casa Inteligente IoT
// ============================================================
//
// HARDWARE REQUERIDO:
//   - ESP32 con módulo LoRa SX1276 integrado (ej. TTGO LoRa32 v2.1)
//     O ESP32 DevKit + módulo LoRa SX1276 por SPI
//   - Sensor BME280 conectado por I²C (SDA=21, SCL=22)
//   - Sensor PIR HC-SR501 (GPIO 25)
//   - LDR con divisor resistivo (GPIO 34, ADC1)
//   - Relés para luz, AC y alarma (GPIO 13, 12, 4)
//
// LIBRERÍAS ARDUINO IDE (instalar por Gestor de Librerías):
//   1. "MCCI LoRaWAN LMIC library" — MCCI Catena
//   2. "Adafruit BME280 Library"   — Adafruit
//   3. "Adafruit Unified Sensor"   — Adafruit (dependencia)
//
// CONFIGURACIÓN PREVIA:
//   1. Editar include/config.h con las credenciales TTN
//   2. Crear lmic_project_config.h (ver abajo)
//   3. Seleccionar placa: ESP32 Dev Module o TTGO LoRa32
//
// lmic_project_config.h (crear en la carpeta del sketch):
//   #define CFG_eu868 1
//   #define CFG_sx1276_radio 1
//   #define LMIC_USE_INTERRUPTS
//
// FLUJO DE EJECUCIÓN:
//   setup(): inicializa periféricos y lanza join OTAA
//   loop():  procesa LMIC y gestiona el ciclo de medición/envío
// ============================================================

#include <Arduino.h>
#include "config.h"
#include "sensor_bme280.h"
#include "cayenne_lpp.h"
#include "lorawan.h"
#include "actuadores.h"

// ---- Variables de control del ciclo principal ----
static unsigned long _ultimo_tx_ms  = 0;
static unsigned long _tx_interval_ms = (unsigned long)TX_INTERVAL_SEC * 1000UL;
static bool          _primer_envio   = true;   // enviar inmediatamente al arrancar
static uint8_t       _errores_bme    = 0;

// Buffer Cayenne LPP (13 bytes para 5 campos: T+H+P+Lux+Presencia)
static CayenneLPP lpp(51);

// ---- Lectura de sensores auxiliares (LDR y PIR) ----

uint16_t leer_luminosidad_lux() {
    // ADC ESP32: 12 bits (0-4095) a 3.3V con atenuación 11dB → 0-3.9V
    // LDR en divisor con R=10kΩ: más luz → menos resistencia → más voltaje
    // Convertir valor ADC a lux (calibración aproximada para LDR 5528)
    int raw = analogRead(LDR_PIN);
    // Escala lineal aproximada: 0 ADC = 0 lux, 4095 ADC ≈ 65535 lux
    // Ajustar constante según tu LDR y resistencia de pull-down
    uint16_t lux = (uint16_t)map(raw, 0, 4095, 0, 1000);
    return lux;
}

uint8_t leer_presencia() {
    // PIR HC-SR501: HIGH = movimiento detectado, LOW = sin movimiento
    // Tiempo de retención configurable con potenciómetro del módulo (5-200s)
    return digitalRead(PIR_PIN) == HIGH ? 1 : 0;
}

// ---- Callback de downlink LoRaWAN ----
// Se llama desde lorawan.cpp cuando llega un mensaje del servidor

void on_downlink(const uint8_t* datos, uint8_t longitud, uint8_t puerto) {
    Serial.printf("[Main] Downlink recibido: %d bytes en puerto %d\n",
                  longitud, puerto);
    for (uint8_t i = 0; i < longitud; i++) {
        Serial.printf("  [%d] 0x%02X\n", i, datos[i]);
    }
    actuadores_procesar_downlink(puerto, datos, longitud);
}

// ---- Función de construcción y envío del payload ----

bool enviar_datos() {
    // 1. Leer BME280
    DatosBME280 bme = bme280_leer();
    if (!bme.validos) {
        _errores_bme++;
        Serial.printf("[Main] Error BME280 (#%d)\n", _errores_bme);
        if (_errores_bme >= 5) {
            Serial.println("[Main] Demasiados errores BME280, reiniciando sensor...");
            bme280_init();
            _errores_bme = 0;
        }
        return false;
    }
    _errores_bme = 0;

    // 2. Leer sensores auxiliares
    uint16_t lux      = leer_luminosidad_lux();
    uint8_t  presencia = leer_presencia();

    Serial.printf("[Main] Lecturas → T=%.1f°C H=%.1f%% P=%.1fhPa Lux=%d Pres=%d\n",
                  bme.temperatura, bme.humedad, bme.presion, lux, presencia);

    // 3. Construir payload Cayenne LPP
    lpp.reset();

    bool ok = true;
    ok &= lpp.addTemperature(LPP_CH_TEMPERATURE,        bme.temperatura);
    ok &= lpp.addHumidity(LPP_CH_HUMIDITY,              bme.humedad);
    ok &= lpp.addBarometricPressure(LPP_CH_PRESSURE,    bme.presion);
    ok &= lpp.addLuminosity(LPP_CH_LUMINOSITY,          lux);
    ok &= lpp.addPresence(LPP_CH_PRESENCE,              presencia);

    if (!ok) {
        Serial.println("[Main] Error: payload LPP demasiado grande");
        return false;
    }

    lpp.printHex(Serial);
    Serial.printf("[Main] Payload: %d bytes · SF%d · habitación %s\n",
                  lpp.getSize(), lorawan_sf(), DEVICE_ROOM_NAME);

    // 4. Enviar por LoRaWAN (FPort = 1 para Cayenne LPP)
    bool encolado = lorawan_enviar(lpp.getBuffer(), lpp.getSize(), 1, false);
    if (!encolado) {
        Serial.println("[Main] No se pudo encolar el envío (LoRaWAN ocupado)");
        return false;
    }

    Serial.println("[Main] Payload encolado correctamente");
    return true;
}

// ---- LED de estado ----

void parpadeo_led(int veces, int duracion_ms = 100) {
    for (int i = 0; i < veces; i++) {
        digitalWrite(LED_PIN, HIGH);
        delay(duracion_ms);
        digitalWrite(LED_PIN, LOW);
        delay(duracion_ms);
    }
}

// ============================================================
// SETUP
// ============================================================
void setup() {
    Serial.begin(115200);
    while (!Serial && millis() < 3000);  // Esperar monitor serie (máx 3s)

    Serial.println("\n================================");
    Serial.printf("  Casa Inteligente IoT v%s\n", FW_VERSION);
    Serial.printf("  Habitación: %s\n", DEVICE_ROOM_NAME);
    Serial.printf("  Intervalo TX: %d s\n", TX_INTERVAL_SEC);
    Serial.println("================================\n");

    // ---- Inicializar LED ----
    pinMode(LED_PIN, OUTPUT);
    parpadeo_led(3, 200);   // 3 parpadeos = inicio

    // ---- Inicializar actuadores ----
    actuadores_init();

    // ---- Inicializar PIR y LDR ----
    pinMode(PIR_PIN, INPUT);
    analogReadResolution(12);         // ADC a 12 bits (0-4095)
    analogSetAttenuation(ADC_11db);   // Rango completo 0-3.9V
    Serial.println("[Main] PIR y LDR inicializados");

    // ---- Inicializar BME280 ----
    if (!bme280_init()) {
        Serial.println("[Main] FALLO CRÍTICO: BME280 no responde");
        Serial.println("[Main] Comprueba el cableado I2C y la dirección (0x76/0x77)");
        // Seguir adelante — enviaremos datos cuando el sensor responda
    }

    // ---- Inicializar LoRaWAN ----
    lorawan_init();
    lorawan_set_downlink_cb(on_downlink);
    lorawan_join();

    Serial.println("[Main] Esperando join OTAA con TTN...");
    parpadeo_led(1, 50);
}

// ============================================================
// LOOP
// ============================================================
void loop() {
    // 1. Mantener LMIC activo (obligatorio)
    lorawan_loop();

    // 2. Gestionar ciclo de envío
    unsigned long ahora = millis();
    bool es_hora_de_enviar = _primer_envio ||
                             (ahora - _ultimo_tx_ms >= _tx_interval_ms);

    if (es_hora_de_enviar && lorawan_listo()) {
        _primer_envio = false;

        bool enviado = enviar_datos();

        if (enviado) {
            _ultimo_tx_ms = ahora;
            digitalWrite(LED_PIN, HIGH);   // LED ON durante TX
        } else {
            // Reintentaremos en el próximo loop
            Serial.println("[Main] Reintentando en el siguiente ciclo...");
        }
    }

    // 3. Apagar LED cuando LMIC no está transmitiendo
    if (lorawan_listo()) {
        digitalWrite(LED_PIN, LOW);
    }

    // 4. Pequeña pausa para no saturar el core
    // LMIC es cooperativo (no usa RTOS), no bloquear más de unos ms
    delay(10);
}
