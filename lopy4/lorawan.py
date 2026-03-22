# lorawan.py — Módulo de conexión LoRaWAN OTAA para LoPy4
# Gestiona el join y la creación del socket de comunicación.

from network import LoRa
import socket
import time
import ubinascii

# ============================================================
# PARÁMETROS DE REGISTRO (obtenidos de The Things Network)
# Sustituir con los valores reales de tu aplicación TTN
# ============================================================

# Caso A: usando el DEV_EUI del dispositivo (introducido en TTN)
APP_EUI = ubinascii.unhexlify('0000000000000000')  # Reemplazar con tu App EUI
APP_KEY = ubinascii.unhexlify('00000000000000000000000000000000')  # Reemplazar con tu App Key

# Caso B: usando DEV_EUI generado por TTN (descomentar si aplica)
# DEV_EUI = ubinascii.unhexlify('XXXXXXXXXXXXXXXX')  # EUI generado por TTN


def conectar_lorawan(reintentos=10):
    """
    Establece la conexión LoRaWAN mediante OTAA.
    Devuelve el socket listo para enviar/recibir datos.
    Parpadea en amarillo mientras intenta conectarse.
    """
    import pycom

    # Inicializar LoRa en modo LoRaWAN región Europa (EU868)
    lora = LoRa(mode=LoRa.LORAWAN, region=LoRa.EU868)

    print("[LoRaWAN] Iniciando join OTAA...")
    pycom.rgbled(0xFFFF00)  # Amarillo: intentando conectar

    # --- Caso A: DEV_EUI del propio dispositivo ---
    lora.join(activation=LoRa.OTAA, auth=(APP_EUI, APP_KEY), timeout=0)

    # --- Caso B: DEV_EUI generado por TTN (descomentar si aplica) ---
    # lora.join(activation=LoRa.OTAA, auth=(DEV_EUI, APP_EUI, APP_KEY), timeout=0)

    # Esperar hasta que el join se complete
    intentos = 0
    while not lora.has_joined():
        time.sleep(2.5)
        intentos += 1
        print("[LoRaWAN] Esperando join... intento {}/{}".format(intentos, reintentos))
        if intentos >= reintentos:
            print("[LoRaWAN] ERROR: No se pudo conectar a la red LoRaWAN")
            pycom.rgbled(0xFF0000)  # Rojo: error
            return None, None

    print("[LoRaWAN] Join completado con éxito")
    pycom.rgbled(0x00FF00)  # Verde: conectado

    # Crear socket LoRa
    s = socket.socket(socket.AF_LORA, socket.SOCK_RAW)
    s.setsockopt(socket.SOL_LORA, socket.SO_DR, 5)  # Data Rate 5
    s.setblocking(True)

    return lora, s


def enviar_datos(s, payload_bytes):
    """
    Envía bytes por el socket LoRaWAN.
    Devuelve los datos de downlink si los hay, o b'' si no.
    """
    try:
        s.send(payload_bytes)
        # Ventana de recepción (downlink)
        s.setblocking(False)
        datos_rx = s.recv(64)
        s.setblocking(True)
        return datos_rx
    except Exception as e:
        print("[LoRaWAN] Error al enviar: {}".format(e))
        return b''
