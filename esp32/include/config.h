#ifndef CONFIG_H
#define CONFIG_H

// ============================================================
// config.h — Configuración de la Casa Inteligente IoT
// ============================================================
// INSTRUCCIONES:
//   1. Copia este fichero y renómbralo config_secret.h
//   2. Rellena las credenciales de TTN
//   3. Ajusta los pines según tu hardware
//   4. config_secret.h está en .gitignore — nunca lo subas a Git
// ============================================================


// ------------------------------------------------------------
// CREDENCIALES TTN (The Things Network)
// Obtenerlas en: TTN Console → Applications → [tu-app] →
//                End devices → [tu-dispositivo] → Overview
// ------------------------------------------------------------

// DevEUI del dispositivo (8 bytes, LSB first para LMIC)
// En TTN se muestra como MSB — invertir byte a byte
#define DEVEUI  { 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00 }

// AppEUI / JoinEUI (8 bytes, LSB first para LMIC)
#define APPEUI  { 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00 }

// AppKey (16 bytes, MSB first — igual que TTN lo muestra)
#define APPKEY  { 0x00,0x00,0x00,0x00, 0x00,0x00,0x00,0x00, \
                  0x00,0x00,0x00,0x00, 0x00,0x00,0x00,0x00 }


// ------------------------------------------------------------
// IDENTIFICACIÓN DEL DISPOSITIVO
// Indica en qué habitación está instalado este ESP32
// Valores válidos: 1=salón 2=cocina 3=dormitorio 4=baño 5=exterior
// ------------------------------------------------------------
#define DEVICE_ROOM       1          // Salón por defecto
#define DEVICE_ROOM_NAME  "salon"


// ------------------------------------------------------------
// PINES — ESP32 ↔ Módulo LoRa SX1276 (TTGO LoRa32 v2.1)
// Si usas otra placa, ajusta estos valores
// ------------------------------------------------------------
#define LORA_SCK    5
#define LORA_MISO   19
#define LORA_MOSI   27
#define LORA_SS     18    // NSS / CS
#define LORA_RST    14
#define LORA_DIO0   26
#define LORA_DIO1   33
#define LORA_DIO2   32

// Pines I²C para BME280 (usa los pines I²C por defecto del ESP32)
#define I2C_SDA     21
#define I2C_SCL     22
#define BME280_ADDR 0x76   // 0x76 o 0x77 según soldadura del pad SDO

// Pin del sensor PIR (presencia/movimiento)
#define PIR_PIN     25

// Pin del LDR (luminosidad, entrada analógica)
// En ESP32 usar pines ADC1 (GPIO 32-39) — ADC2 no funciona con WiFi activo
#define LDR_PIN     34    // ADC1_CH6, solo entrada

// Pines de actuadores (relés — HIGH = activo)
#define RELAY_LUZ    13
#define RELAY_AC     12
#define RELAY_ALARMA  4

// LED de estado incorporado (TTGO LoRa32 = GPIO 25, ESP32 DevKit = GPIO 2)
#define LED_PIN      2


// ------------------------------------------------------------
// PARÁMETROS DE COMPORTAMIENTO
// ------------------------------------------------------------

// Intervalo entre envíos de datos en segundos
// Duty cycle EU868 = 1% → máx 36 s/hora de TX
// Con SF7 + 13 bytes payload ≈ 0.25 s/envío → máx ~144 envíos/día
// 15 minutos = 96 envíos/día → margen seguro
#define TX_INTERVAL_SEC   900     // 15 minutos

// Número de reintentos de join antes de reset
#define JOIN_MAX_RETRIES  20

// Canal Cayenne LPP para cada sensor (1–99)
#define LPP_CH_TEMPERATURE  1
#define LPP_CH_HUMIDITY     2
#define LPP_CH_PRESSURE     3
#define LPP_CH_LUMINOSITY   4
#define LPP_CH_PRESENCE     5

// Versión del firmware (para debug)
#define FW_VERSION  "1.0.0"

#endif // CONFIG_H
