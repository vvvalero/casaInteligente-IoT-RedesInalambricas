# credentials.example.py — Plantilla de credenciales TTN
# ============================================================
# INSTRUCCIONES:
#   1. Copia este fichero: cp credentials.example.py credentials.py
#   2. Rellena los valores con los de TTN Console
#   3. NUNCA subas credentials.py a GitHub (está en .gitignore)
#
# Dónde obtener los valores:
#   TTN Console → Applications → [tu-app] →
#   End devices → [tu-dispositivo] → Overview
#
# IMPORTANTE sobre el formato:
#   - APP_EUI y APP_KEY se copian tal cual aparecen en TTN (MSB)
#   - Elimina los espacios: 'AD A4 DA...' → 'ADA4DA...'
# ============================================================

import binascii

# AppEUI / JoinEUI (8 bytes, MSB, sin espacios)
APP_EUI = binascii.unhexlify('XXXXXXXXXXXXXXXX')

# AppKey (16 bytes, MSB, sin espacios)
APP_KEY = binascii.unhexlify('XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX')

# Habitación donde está instalado este dispositivo
# 1=salon  2=cocina  3=dormitorio  4=bano  5=exterior
DEVICE_ROOM = 1

# Intervalo entre envíos en segundos
# Pruebas: 60  |  Producción: 900 (15 min, respeta duty cycle TTN)
TX_INTERVAL = 60
