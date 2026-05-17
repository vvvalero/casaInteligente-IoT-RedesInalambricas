# led.py — Control del LED RGB integrado en el LoPy4
# ============================================================
# El LoPy4 tiene un LED RGB integrado controlado con pycom.rgbled()
# Se usa para indicar tanto el estado del sistema como
# los eventos recibidos por downlink desde Fiware.
#
# Colores de estado del sistema (LED tenue para no molestar):
#   Azul tenue    → arrancando
#   Rojo parpadeante → esperando join OTAA
#   Verde tenue   → conectado, en espera
#   Blanco destello → transmitiendo uplink
#   Rojo fijo     → error crítico
#   Cian destello → downlink recibido
#
# Colores de eventos (LED más brillante):
#   Naranja       → alerta temperatura alta
#   Azul cian     → alerta temperatura baja
#   Magenta       → vibración detectada
#   Amarillo      → alerta aforo BLE
#   Verde         → acceso NFC concedido
#   Rojo          → acceso NFC denegado
#   Blanco        → alerta luminosidad exterior
# ============================================================

import pycom
import time

# Detectar si estamos en hardware real
_HARDWARE_AVAILABLE = True
try:
    pycom.rgbled(0x000000)  # Test
except (OSError, AttributeError):
    _HARDWARE_AVAILABLE = False
    print("[LED] Advertencia: LED RGB no disponible (probablemente simulación)")


def sistema_arrancando():
    if _HARDWARE_AVAILABLE:
        try:
            pycom.rgbled(0x000010)
        except OSError:
            pass


def sistema_join_espera():
    if _HARDWARE_AVAILABLE:
        try:
            pycom.rgbled(0x100000)
        except OSError:
            pass


def sistema_conectado():
    if _HARDWARE_AVAILABLE:
        try:
            pycom.rgbled(0x001000)
        except OSError:
            pass


def sistema_transmitiendo():
    if _HARDWARE_AVAILABLE:
        try:
            pycom.rgbled(0x101010)
            time.sleep(0.1)
            pycom.rgbled(0x001000)
        except OSError:
            pass


def sistema_error():
    if _HARDWARE_AVAILABLE:
        try:
            pycom.rgbled(0xFF0000)
        except OSError:
            pass


def sistema_downlink_recibido():
    if _HARDWARE_AVAILABLE:
        try:
            pycom.rgbled(0x00FFFF)
            time.sleep(0.2)
            pycom.rgbled(0x001000)
        except OSError:
            pass


def led_apagar():
    if _HARDWARE_AVAILABLE:
        try:
            pycom.rgbled(0x000000)
        except OSError:
            pass


def led_rojo():
    if _HARDWARE_AVAILABLE:
        try:
            pycom.rgbled(0xFF0000)
        except OSError:
            pass


def led_verde():
    if _HARDWARE_AVAILABLE:
        try:
            pycom.rgbled(0x00FF00)
        except OSError:
            pass


def led_azul():
    if _HARDWARE_AVAILABLE:
        try:
            pycom.rgbled(0x0000FF)
        except OSError:
            pass


def led_amarillo():
    if _HARDWARE_AVAILABLE:
        try:
            pycom.rgbled(0xFFFF00)
        except OSError:
            pass


def led_naranja():
    if _HARDWARE_AVAILABLE:
        try:
            pycom.rgbled(0xFF4400)
        except OSError:
            pass


def led_magenta():
    if _HARDWARE_AVAILABLE:
        try:
            pycom.rgbled(0xFF00FF)
        except OSError:
            pass


def led_blanco():
    if _HARDWARE_AVAILABLE:
        try:
            pycom.rgbled(0xFFFFFF)
        except OSError:
            pass


def led_desde_bytes(r, g, b):
    """
    Establece el color del LED desde bytes de downlink.
    r, g, b: valores 0-255 recibidos del servidor.
    """
    color = (r << 16) | (g << 8) | b
    if _HARDWARE_AVAILABLE:
        try:
            pycom.rgbled(color)
        except OSError:
            pass
    print('[LED] Color RGB: #{:06X}'.format(color))


def parpadear(funcion_color, veces=3, intervalo=0.3):
    """
    Hace parpadear un color N veces y vuelve a verde (conectado).
    funcion_color: una de las funciones led_* de este módulo.
    """
    if _HARDWARE_AVAILABLE:
        for _ in range(veces):
            funcion_color()
            time.sleep(intervalo)
            led_apagar()
            time.sleep(intervalo)
        sistema_conectado()


def obtener_color_actual():
    """Retorna el color actual del LED como entero RGB."""
    if _HARDWARE_AVAILABLE:
        try:
            return pycom.rgbled()
        except OSError:
            return 0x000000
    return 0x000000
