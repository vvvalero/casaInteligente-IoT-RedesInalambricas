# actuadores.py — Control de actuadores para LoPy4
#
# Actuadores implementados:
#   - Lámpara/Iluminación : relé en pin P21 (HIGH = encendido)
#   - Aire Acondicionado  : relé en pin P20 (HIGH = encendido)
#   - Alarma/Seguridad    : buzzer/relé en pin P19 (HIGH = activada)
#
# Adaptá los pines según tu cableado real.
#
# USO desde main.py:
#   from actuadores import ejecutar_comando
#   ...
#   if len(data) >= 2:
#       ejecutar_comando({'comando': CMDS[data[0]], 'valor': data[1]})

from machine import Pin
import pycom

# ---- Pines de salida ----
PIN_LUZ    = 'P21'
PIN_AC     = 'P20'
PIN_ALARMA = 'P19'

# Inicializar pines de salida (todo apagado al arrancar)
pin_luz    = Pin(PIN_LUZ,    mode=Pin.OUT, value=0)
pin_ac     = Pin(PIN_AC,     mode=Pin.OUT, value=0)
pin_alarma = Pin(PIN_ALARMA, mode=Pin.OUT, value=0)

# Estado actual de los actuadores
estado = {
    'luz':    0,
    'ac':     0,
    'alarma': 0,
}

# Mapa de comandos downlink (byte 0 del payload)
CMDS = {
    0x01: 'luz',
    0x02: 'ac',
    0x03: 'alarma',
}


def _actualizar_led():
    """Actualiza el LED RGB del LoPy4 para reflejar el estado global."""
    if estado['alarma']:
        pycom.rgbled(0xFF0000)   # Rojo: alarma activa
    elif estado['ac'] and estado['luz']:
        pycom.rgbled(0x00FFFF)   # Cian: luz + AC
    elif estado['luz']:
        pycom.rgbled(0xFFFF00)   # Amarillo: solo luz
    elif estado['ac']:
        pycom.rgbled(0x0000FF)   # Azul: solo AC
    else:
        pycom.rgbled(0x007f00)   # Verde: todo apagado (conectado)


def controlar_luz(valor):
    """Enciende (1) o apaga (0) la lámpara."""
    estado['luz'] = 1 if valor else 0
    pin_luz.value(estado['luz'])
    _actualizar_led()
    print('[Actuadores] Luz: {}'.format('ON' if estado['luz'] else 'OFF'))


def controlar_ac(valor):
    """Enciende (1) o apaga (0) el aire acondicionado."""
    estado['ac'] = 1 if valor else 0
    pin_ac.value(estado['ac'])
    _actualizar_led()
    print('[Actuadores] AC: {}'.format('ON' if estado['ac'] else 'OFF'))


def controlar_alarma(valor):
    """Activa (1) o desactiva (0) la alarma."""
    estado['alarma'] = 1 if valor else 0
    pin_alarma.value(estado['alarma'])
    _actualizar_led()
    print('[Actuadores] Alarma: {}'.format('ACTIVA' if estado['alarma'] else 'DESACTIVADA'))


def ejecutar_comando(comando_dict):
    """
    Despacha un comando recibido del downlink LoRaWAN.
    Args:
        comando_dict (dict): {'comando': str, 'valor': int}
    """
    if not comando_dict:
        return
    cmd   = comando_dict.get('comando', '')
    valor = comando_dict.get('valor', 0)

    if cmd == 'luz':
        controlar_luz(valor)
    elif cmd == 'ac':
        controlar_ac(valor)
    elif cmd == 'alarma':
        controlar_alarma(valor)
    else:
        print('[Actuadores] Comando desconocido: {}'.format(cmd))


def obtener_estado():
    """Retorna el estado actual de todos los actuadores."""
    return dict(estado)
