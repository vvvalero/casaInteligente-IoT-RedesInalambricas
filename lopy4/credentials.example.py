# credentials.example.py — Plantilla de credenciales y configuración
# ============================================================
# INSTRUCCIONES:
#   1. Copia: cp credentials.example.py credentials.py
#   2. Rellena los valores con los de TTN Console
#   3. NUNCA subas credentials.py a GitHub
#
# NODE_TYPE define el comportamiento completo del nodo:
#   'salon'      → Nodo 1: sensores completos + acelerómetro + LED RGB
#   'dormitorio' → Nodo 2: sensores + NFC PN532 + LED acceso
#   'exterior'   → Nodo 3: sensores + BLE scanner + LED alerta
# ============================================================

import binascii

# Credenciales TTN
APP_EUI = binascii.unhexlify('XXXXXXXXXXXXXXXX')
APP_KEY = binascii.unhexlify('XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX')

# Tipo de nodo — define qué sensores y comportamiento activa
# Valores válidos: 'salon' | 'dormitorio' | 'exterior'
NODE_TYPE = 'salon'

# Intervalo entre envíos en segundos
# Pruebas: 60  |  Producción: 900
TX_INTERVAL = 60
