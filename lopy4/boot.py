# boot.py — LoPy4 Smart Home IoT
# Se ejecuta al arrancar el dispositivo.
# Configura el modo de depuración y deshabilita el heartbeat LED.

import pycom
import machine

# Desactivar el LED de heartbeat para ahorrar energía
pycom.heartbeat(False)

# Parpadeo azul al arrancar: dispositivo iniciando
pycom.rgbled(0x0000FF)

print("=== Smart Home LoPy4 - Arrancando ===")
