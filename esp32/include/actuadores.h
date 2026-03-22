#ifndef ACTUADORES_H
#define ACTUADORES_H

// ============================================================
// actuadores.h — Control de relés y actuadores
// ============================================================

#include <Arduino.h>

// Inicializa los pines de los actuadores
void actuadores_init();

// Control individual
void actuador_luz(bool encendido);
void actuador_ac(bool encendido);
void actuador_alarma(bool activada);

// Despacha un comando recibido por downlink LoRaWAN
// puerto:  FPort del downlink (1 = comandos de actuador)
// datos:   bytes del payload descifrado
// longitud: número de bytes
void actuadores_procesar_downlink(uint8_t puerto,
                                  const uint8_t* datos,
                                  uint8_t longitud);

// Retorna estado actual (para logging/debug)
bool actuador_estado_luz();
bool actuador_estado_ac();
bool actuador_estado_alarma();

#endif
