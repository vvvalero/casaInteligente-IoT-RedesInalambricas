# main.py — Casa Inteligente IoT · LoPy4 + Pysense
# ============================================================
# HARDWARE:
#   - LoPy4 con placa de expansión Pysense
#   - SI7006A20   → temperatura + humedad (I²C, en Pysense)
#   - LTR329ALS01 → luminosidad (I²C, en Pysense)
#
# ANTES DE SUBIR AL DISPOSITIVO:
#   1. Copia credentials.example.py → credentials.py
#   2. Rellena APP_EUI, APP_KEY y DEVICE_ROOM en credentials.py
#   3. Sube con Pymakr: Upload project to device
#   4. Verifica join en TTN Console → Live data
# ============================================================

import socket
import time
import binascii
import pycom
from network import LoRa
from CayenneLPP import CayenneLPP
from pysense import Pysense
from SI7006A20 import SI7006A20
from LTR329ALS01 import LTR329ALS01

# ============================================================
# CREDENCIALES Y CONFIGURACIÓN (desde credentials.py)
# ============================================================
try:
    from credentials import APP_EUI, APP_KEY, DEVICE_ROOM, TX_INTERVAL
except ImportError:
    print('ERROR: credentials.py no encontrado.')
    print('Copia credentials.example.py a credentials.py y rellena tus datos TTN.')
    import sys
    sys.exit()

# ============================================================
# INICIALIZACIÓN DE HARDWARE
# ============================================================
pycom.heartbeat(False)
pycom.rgbled(0x140000)  # Rojo tenue: arrancando

py = Pysense()
si = SI7006A20(py)    # Temperatura + Humedad
lt = LTR329ALS01(py)  # Luminosidad

print('=== Casa Inteligente IoT ===')
print('Habitacion: {}'.format(DEVICE_ROOM))
print('Intervalo TX: {} s'.format(TX_INTERVAL))
print('DevEUI: {}'.format(binascii.hexlify(LoRa().mac()).decode('utf-8').upper()))

# ============================================================
# CONEXIÓN LORAWAN (OTAA)
# ============================================================
lora = LoRa(mode=LoRa.LORAWAN, region=LoRa.EU868)
lora.join(activation=LoRa.OTAA, auth=(APP_EUI, APP_KEY), timeout=0)

print('Intentando join OTAA...')
while not lora.has_joined():
    pycom.rgbled(0x140000)  # Rojo: esperando join
    time.sleep(2.5)
    pycom.rgbled(0x000000)
    time.sleep(1.0)
    print('  Esperando join...')

print('Join completado!')
pycom.rgbled(0x007f00)  # Verde: conectado

# Socket LoRaWAN (DR5 = SF7 BW125, maxima velocidad EU868)
s = socket.socket(socket.AF_LORA, socket.SOCK_RAW)
s.setsockopt(socket.SOL_LORA, socket.SO_DR, 5)

# ============================================================
# BUCLE PRINCIPAL
# ============================================================
while True:
    # ---- 1. Leer sensores ----
    temperatura = si.temperature()
    humedad     = si.humidity()
    luminosidad = lt.light()[0]  # Canal visible en lux

    print('\n--- Nueva lectura ---')
    print('  Temperatura:  {:.1f} C'.format(temperatura))
    print('  Humedad:      {:.1f} %'.format(humedad))
    print('  Luminosidad:  {} lux'.format(luminosidad))
    print('  Habitacion:   {}'.format(DEVICE_ROOM))

    # ---- 2. Codificar con Cayenne LPP ----
    lpp = CayenneLPP()
    lpp.add_temperature(1, temperatura)        # Canal 1: temperatura
    lpp.add_relative_humidity(2, humedad)      # Canal 2: humedad
    lpp.add_luminosity(3, luminosidad)         # Canal 3: luminosidad
    lpp.add_digital_input(4, DEVICE_ROOM)      # Canal 4: ID habitacion

    payload = bytes(lpp.get_buffer())
    print('  Payload ({} bytes): {}'.format(
        len(payload),
        binascii.hexlify(payload).decode('utf-8').upper()
    ))

    # ---- 3. Enviar uplink ----
    s.setblocking(True)   # Espera TX + ventanas RX1/RX2
    s.send(payload)
    print('  Uplink enviado')
    pycom.rgbled(0x00007f)  # Azul: transmitiendo

    # ---- 4. Leer posible downlink ----
    # Protocolo downlink (2 bytes): [cmd, valor]
    #   0x01 = luz    (0=OFF, 1=ON)
    #   0x02 = AC     (0=OFF, 1=ON)
    #   0x03 = alarma (0=OFF, 1=ON)
    s.setblocking(False)
    data = s.recv(64)

    if data:
        print('  Downlink recibido: {}'.format(
            binascii.hexlify(data).decode('utf-8').upper()
        ))
        if len(data) >= 2:
            cmd   = data[0]
            valor = data[1]
            print('  Comando: cmd=0x{:02X} valor={}'.format(cmd, valor))
    else:
        print('  Sin downlink')

    # ---- 5. LED de estado ----
    pycom.rgbled(0x007f00)  # Verde: en espera

    # ---- 6. Esperar hasta el proximo ciclo ----
    print('  Siguiente envio en {} s'.format(TX_INTERVAL))
    time.sleep(TX_INTERVAL)
