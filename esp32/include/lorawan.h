#ifndef LORAWAN_H
#define LORAWAN_H

// ============================================================
// lorawan.h — Capa de abstracción LoRaWAN sobre LMIC
// ============================================================
// Librería requerida: "MCCI LoRaWAN LMIC library" de MCCI Catena
// Instalar en Arduino IDE → Gestor de librerías →
//   buscar "MCCI LoRaWAN LMIC library"
//
// Esta capa abstrae la complejidad de LMIC y expone una API
// sencilla: init → joinOTAA → enviar → gestionar downlink
// ============================================================

#include <Arduino.h>
#include <stdint.h>

// Estado de la capa LoRaWAN
enum class EstadoLoRa {
    DESCONECTADO,     // Sin join
    UNIENDO,          // Join en progreso
    CONECTADO,        // Join completado, listo para TX
    ENVIANDO,         // TX en curso
    ERROR_JOIN,       // Join fallido
    ERROR_TX          // TX fallida
};

// Callback invocado cuando llega un downlink
// Parámetros: puntero a los bytes recibidos y longitud
typedef void (*DownlinkCallback)(const uint8_t* datos, uint8_t longitud, uint8_t puerto);

// ---- API pública ----

// Inicializa LMIC y los pines del módulo LoRa
// Debe llamarse en setup() antes de cualquier otra función
void lorawan_init();

// Inicia el proceso de join OTAA (no bloqueante)
// Retorna inmediatamente; el join ocurre en segundo plano via LMIC
void lorawan_join();

// Retorna el estado actual de la conexión LoRaWAN
EstadoLoRa lorawan_estado();

// Envía un payload uplink (no bloqueante)
// payload: puntero a los bytes a enviar
// len:     número de bytes (máx. según SF y BW)
// puerto:  FPort LoRaWAN (1-223); usa 1 para Cayenne LPP
// confirmar: true = envío confirmado (ACK del servidor)
// Retorna true si el envío fue encolado, false si LMIC está ocupado
bool lorawan_enviar(const uint8_t* payload, uint8_t len,
                    uint8_t puerto = 1, bool confirmar = false);

// Registra el callback que se llama al recibir un downlink
void lorawan_set_downlink_cb(DownlinkCallback cb);

// Debe llamarse periódicamente en loop() para que LMIC procese eventos
// Internamente llama a os_runloop_once()
void lorawan_loop();

// Retorna true si el módulo puede enviar ahora (no hay TX pendiente)
bool lorawan_listo();

// Retorna el RSSI y SNR del último uplink recibido por el gateway
// (disponibles tras un TX confirmado con ACK)
int  lorawan_rssi();
int  lorawan_snr();

// Retorna el Spreading Factor activo (7-12)
uint8_t lorawan_sf();

#endif // LORAWAN_H
