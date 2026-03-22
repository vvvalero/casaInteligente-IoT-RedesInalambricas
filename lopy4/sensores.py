# sensores.py — Módulo de lectura de sensores para LoPy4
#
# Sensores implementados:
#   - Temperatura + Humedad: DHT22 (pin P23)
#   - Luminosidad:           LDR vía ADC (pin P16)
#   - Presencia/Movimiento:  PIR digital (pin P22)
#
# Adaptá los pines según tu cableado real.

from machine import Pin, ADC
import time

# ---- Pines de conexión ----
PIN_DHT    = 'P23'   # DHT22 - Temperatura y Humedad
PIN_LDR    = 'P16'   # LDR   - Luminosidad (entrada analógica)
PIN_PIR    = 'P22'   # PIR   - Presencia/Movimiento (digital)


# -----------------------------------------------------------
# DHT22: Temperatura y Humedad
# Librería dht incluida en el firmware de Pycom
# -----------------------------------------------------------
try:
    import dht
    sensor_dht = dht.DHT22(Pin(PIN_DHT))
    DHT_DISPONIBLE = True
except Exception:
    DHT_DISPONIBLE = False
    print("[Sensores] AVISO: DHT22 no disponible, usando valores simulados")


def leer_temperatura_humedad():
    """
    Lee temperatura (°C) y humedad (%) del DHT22.
    Si el sensor no está disponible, devuelve valores simulados.
    Retorna: (temperatura: float, humedad: float)
    """
    if DHT_DISPONIBLE:
        try:
            sensor_dht.measure()
            temp = sensor_dht.temperature()
            hum  = sensor_dht.humidity()
            return round(temp, 1), round(hum, 1)
        except Exception as e:
            print("[Sensores] Error DHT22: {}".format(e))

    # Valores simulados para desarrollo/pruebas
    import math, time
    t = time.time()
    temp_sim = 22.0 + 3.0 * math.sin(t / 300.0)
    hum_sim  = 55.0 + 10.0 * math.sin(t / 600.0 + 1.0)
    return round(temp_sim, 1), round(hum_sim, 1)


# -----------------------------------------------------------
# LDR: Luminosidad (0-100 %)
# -----------------------------------------------------------
adc = ADC()
canal_ldr = adc.channel(pin=PIN_LDR, attn=ADC.ATTN_11DB)


def leer_luminosidad():
    """
    Lee el nivel de luz del LDR como porcentaje (0-100).
    El LDR baja su resistencia con más luz → sube el voltaje ADC.
    Retorna: luminosidad (int, 0-100)
    """
    try:
        valor_raw = canal_ldr.value()   # 0 - 4095 (12 bits)
        porcentaje = int((valor_raw / 4095.0) * 100)
        return porcentaje
    except Exception as e:
        print("[Sensores] Error LDR: {}".format(e))
        return 50  # valor por defecto


# -----------------------------------------------------------
# PIR: Presencia / Movimiento (digital)
# -----------------------------------------------------------
pin_pir = Pin(PIN_PIR, mode=Pin.IN)


def leer_presencia():
    """
    Lee el sensor PIR de presencia.
    Retorna: 1 si hay movimiento detectado, 0 si no.
    """
    try:
        return 1 if pin_pir.value() else 0
    except Exception as e:
        print("[Sensores] Error PIR: {}".format(e))
        return 0


# -----------------------------------------------------------
# Lectura conjunta de todos los sensores
# -----------------------------------------------------------
def leer_todos():
    """
    Realiza una lectura completa de todos los sensores.
    Retorna un diccionario con los valores actuales.
    """
    temp, hum = leer_temperatura_humedad()
    lux       = leer_luminosidad()
    presencia = leer_presencia()

    datos = {
        'temperatura': temp,
        'humedad':     hum,
        'luminosidad': lux,
        'presencia':   presencia
    }
    print("[Sensores] Lectura: {}".format(datos))
    return datos
