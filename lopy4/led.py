# led.py — Control de LEDs externos en protoboard
# ============================================================
# LEDs individuales conectados a pines GPIO del LoPy4:
#   PIN_LED_R → LED rojo   (con resistencia 220Ω a GND)
#   PIN_LED_G → LED verde  (con resistencia 220Ω a GND)
#   PIN_LED_B → LED azul   (con resistencia 220Ω a GND)
#
# El LED RGB interno del LoPy4 se usa para estado del sistema.
# Los LEDs externos en protoboard se usan para señalización
# de eventos recibidos por downlink desde Fiware.
#
# Conexión física:
#   LoPy4 P2 → R 220Ω → LED rojo   → GND
#   LoPy4 P3 → R 220Ω → LED verde  → GND
#   LoPy4 P4 → R 220Ω → LED azul   → GND
# ============================================================

import pycom
from machine import Pin, PWM
import time

# ---- Pines LEDs externos ----
PIN_LED_R = 'P2'
PIN_LED_G = 'P3'
PIN_LED_B = 'P4'

# Inicializar pines como salida digital
_pin_r = Pin(PIN_LED_R, mode=Pin.OUT, value=0)
_pin_g = Pin(PIN_LED_G, mode=Pin.OUT, value=0)
_pin_b = Pin(PIN_LED_B, mode=Pin.OUT, value=0)

# Estado actual
_estado_externo = {'r': 0, 'g': 0, 'b': 0}


# ============================================================
# LED INTERNO (RGB integrado en LoPy4)
# Usado exclusivamente para estado del sistema
# ============================================================

def sistema_arrancando():
    """Azul: dispositivo iniciando."""
    pycom.rgbled(0x000010)

def sistema_join_espera():
    """Rojo parpadeante: esperando join OTAA."""
    pycom.rgbled(0x100000)

def sistema_conectado():
    """Verde tenue: conectado y en espera."""
    pycom.rgbled(0x001000)

def sistema_transmitiendo():
    """Blanco destello: enviando uplink."""
    pycom.rgbled(0x101010)
    time.sleep(0.1)
    pycom.rgbled(0x001000)

def sistema_error():
    """Rojo fijo: error crítico."""
    pycom.rgbled(0xFF0000)

def sistema_downlink_recibido():
    """Cian destello: downlink procesado."""
    pycom.rgbled(0x00FFFF)
    time.sleep(0.2)
    pycom.rgbled(0x001000)


# ============================================================
# LEDs EXTERNOS (protoboard)
# Controlados por downlink desde Fiware
# ============================================================

def _set_leds(r, g, b):
    """Establece el estado de los tres LEDs externos."""
    _estado_externo['r'] = 1 if r else 0
    _estado_externo['g'] = 1 if g else 0
    _estado_externo['b'] = 1 if b else 0
    _pin_r.value(_estado_externo['r'])
    _pin_g.value(_estado_externo['g'])
    _pin_b.value(_estado_externo['b'])


def leds_apagar():
    """Apaga todos los LEDs externos."""
    _set_leds(0, 0, 0)


def led_rojo():
    """LED rojo: acceso denegado / alerta crítica."""
    _set_leds(1, 0, 0)


def led_verde():
    """LED verde: acceso concedido / estado OK."""
    _set_leds(0, 1, 0)


def led_azul():
    """LED azul: alerta frío / información."""
    _set_leds(0, 0, 1)


def led_amarillo():
    """LED amarillo (R+G): alerta aforo / aviso."""
    _set_leds(1, 1, 0)


def led_naranja():
    """LED naranja (R fuerte + G tenue): alerta calor."""
    _pin_r.value(1)
    _pin_g.value(1)   # ambos encendidos = naranja aproximado
    _pin_b.value(0)
    _estado_externo.update({'r': 1, 'g': 1, 'b': 0})


def led_magenta():
    """LED magenta (R+B): alerta vibración."""
    _set_leds(1, 0, 1)


def led_blanco():
    """LED blanco (R+G+B): alerta luminosidad exterior."""
    _set_leds(1, 1, 1)


def led_desde_bytes(r, g, b):
    """
    Establece LEDs desde bytes de downlink (0-255 → umbral 128).
    r, g, b: valores 0-255 recibidos del servidor.
    """
    _set_leds(r > 127, g > 127, b > 127)
    print('[LED] Externo R={} G={} B={}'.format(
        _estado_externo['r'], _estado_externo['g'], _estado_externo['b']))


def parpadear(funcion_color, veces=3, intervalo=0.3):
    """
    Hace parpadear un color N veces.
    funcion_color: una de las funciones led_* de este módulo.
    """
    for _ in range(veces):
        funcion_color()
        time.sleep(intervalo)
        leds_apagar()
        time.sleep(intervalo)


def obtener_estado():
    """Retorna el estado actual de los LEDs externos."""
    return dict(_estado_externo)
