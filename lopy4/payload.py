# payload.py — Codificación y decodificación de mensajes LoRaWAN
#
# Formato del payload uplink (11 bytes):
#
#  Byte 0-1 : Temperatura  → int16, multiplicado x10  (ej: 22.5°C → 225)
#  Byte 2-3 : Humedad      → uint16, multiplicado x10 (ej: 55.4%  → 554)
#  Byte 4   : Luminosidad  → uint8,  0-100 %
#  Byte 5   : Presencia    → uint8,  0 = no, 1 = sí
#  Byte 6   : ID habitación → uint8  (ver tabla HABITACIONES)
#  Byte 7   : Reservado    → 0x00
#
# Formato del payload downlink (2 bytes):
#
#  Byte 0: Comando actuador (ver tabla COMANDOS)
#  Byte 1: Valor del comando
#
# Tabla HABITACIONES:
#   0x01 = Salón
#   0x02 = Cocina
#   0x03 = Dormitorio principal
#   0x04 = Baño
#   0x05 = Exterior/Jardín
#
# Tabla COMANDOS actuador (downlink):
#   0x01 = Luz ON/OFF       (valor: 0 = OFF, 1 = ON)
#   0x02 = AC ON/OFF        (valor: 0 = OFF, 1 = ON)
#   0x03 = Alarma ON/OFF    (valor: 0 = OFF, 1 = ON)
#   0x04 = Nivel luz        (valor: 0-100 %)

import struct

# Mapa de habitaciones
HABITACIONES = {
    'salon':      0x01,
    'cocina':     0x02,
    'dormitorio': 0x03,
    'bano':       0x04,
    'exterior':   0x05,
}

# Mapa de comandos downlink
COMANDOS = {
    0x01: 'luz',
    0x02: 'ac',
    0x03: 'alarma',
    0x04: 'nivel_luz',
}


def codificar_uplink(datos, habitacion='salon'):
    """
    Convierte el diccionario de sensores en bytes para enviar por LoRaWAN.

    Args:
        datos (dict): {'temperatura': float, 'humedad': float,
                       'luminosidad': int, 'presencia': int}
        habitacion (str): clave del mapa HABITACIONES

    Retorna: bytes de 8 bytes listos para enviar
    """
    temp_raw  = int(datos['temperatura'] * 10)   # int16
    hum_raw   = int(datos['humedad'] * 10)        # uint16
    lux_raw   = int(datos['luminosidad'])          # uint8, clamp 0-100
    pres_raw  = int(datos['presencia'])            # uint8, 0 o 1
    hab_raw   = HABITACIONES.get(habitacion, 0x01) # uint8

    # Clamp de valores
    lux_raw  = max(0, min(100, lux_raw))
    pres_raw = max(0, min(1,   pres_raw))

    # Empaquetar: big-endian, int16 + uint16 + uint8 x4
    payload = struct.pack('>hHBBBB',
                          temp_raw,
                          hum_raw,
                          lux_raw,
                          pres_raw,
                          hab_raw,
                          0x00)   # reservado
    return payload


def decodificar_downlink(datos_bytes):
    """
    Interpreta los bytes recibidos del downlink (comando del servidor).

    Args:
        datos_bytes (bytes): 2 bytes recibidos

    Retorna: dict {'comando': str, 'valor': int} o None si no hay datos
    """
    if not datos_bytes or len(datos_bytes) < 2:
        return None

    cmd_id = datos_bytes[0]
    valor  = datos_bytes[1]
    nombre = COMANDOS.get(cmd_id, 'desconocido')

    resultado = {'comando': nombre, 'valor': valor}
    print("[Payload] Comando recibido: {} = {}".format(nombre, valor))
    return resultado
