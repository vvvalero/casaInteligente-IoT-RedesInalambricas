# credentials.example.py — Plantilla de credenciales y configuración
# ============================================================
# INSTRUCCIONES:
#   1. Copia: cp credentials.example.py credentials.py
#   2. Rellena los valores con los de TTN Console
#   3. NUNCA subas credentials.py a GitHub
#
# NODE_TYPE define el comportamiento completo del nodo:
#   'salon'      → Nodo 1: sensores completos + acelerómetro + LED RGB
#   'dormitorio' → Nodo 2: sensores + NFC vía BLE (ESP32+PN532) + LED acceso
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

# MAC del ESP32-NFC (solo para NODE_TYPE='dormitorio')
# Consúltala en el Monitor Serie del ESP32 tras el primer arranque:
#   "[BLE] Anunciando. MAC: AA:BB:CC:DD:EE:FF"
# Formato: 'AA:BB:CC:DD:EE:FF' (mayúsculas, con separadores)
ESP32_NFC_MAC = 'AA:BB:CC:DD:EE:FF'

# Whitelist local de UIDs autorizados (solo los 16 bits bajos, 4 chars hex).
# El ESP32 imprime el UID completo por Serie; usa los últimos 4 chars.
# Ejemplo: UID completo "A1B2C3D4" → clave "C3D4"
# Se sobreescribe automáticamente vía downlink 0x08 cuando se modifica desde el servidor.
NFC_WHITELIST_DEFAULT = ['C3D4', 'BEEF']
