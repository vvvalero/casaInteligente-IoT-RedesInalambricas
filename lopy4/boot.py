# boot.py — LoPy4 Smart Home IoT

import pycom
import machine

pycom.heartbeat(False)  # el heartbeat consume y molesta
pycom.rgbled(0x0000FF)  # azul = arrancando

print("=== Smart Home LoPy4 - Arrancando ===")
