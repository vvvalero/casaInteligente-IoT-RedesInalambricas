// ============================================================
// lmic_project_config.h
// ============================================================
// COPIAR este fichero a la misma carpeta que smart_home_esp32.ino
//
// Este fichero configura la librería MCCI LMIC para:
//   - Región EU868 (Europa 868 MHz)
//   - Chip de radio SX1276 (compatible SX1278, RFM95)
//   - Uso de interrupciones hardware para DIO0/DIO1/DIO2
//
// IMPORTANTE: no modificar estos valores a menos que uses
// hardware diferente (SX1261, AS923, etc.)
// ============================================================

// Región de frecuencias: Europa 868 MHz
// Alternativas: CFG_us915, CFG_au915, CFG_as923, CFG_kr920, CFG_in866
#define CFG_eu868 1

// Chip de radio LoRa
// SX1276/SX1278/RFM95: CFG_sx1276_radio
// SX1261/SX1262:       CFG_sx1261_radio
#define CFG_sx1276_radio 1

// Usar interrupciones hardware en lugar de polling
// Mejora la precisión del timing LoRaWAN
#define LMIC_USE_INTERRUPTS

// Reducir uso de RAM eliminando soporte de clases B y C
// (solo usamos Clase A: TX seguido de dos ventanas RX)
#define DISABLE_BEACONS
#define DISABLE_PING

// Habilitar soporte de aceptación de join en cualquier canal
// (necesario para TTN que usa 3 canales principales)
// No descomentar — LMIC EU868 ya lo gestiona automáticamente

// Tamaño máximo del payload (en bytes) para cada SF
// SF7: 222 bytes | SF8: 222 | SF9: 115 | SF10: 51 | SF11: 51 | SF12: 51
// Nuestro payload Cayenne LPP = 15 bytes → válido en todos los SF
