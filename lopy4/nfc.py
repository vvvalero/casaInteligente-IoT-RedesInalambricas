# nfc.py — Driver PN532 para LoPy4 vía I²C
# ============================================================
# Conexión física (PN532 en modo I²C):
#   PN532 SDA → LoPy4 P9
#   PN532 SCL → LoPy4 P10
#   PN532 VCC → 3.3V
#   PN532 GND → GND
#   PN532 IRQ → LoPy4 P11  (opcional, para lectura no bloqueante)
#
# IMPORTANTE: en el módulo PN532, los interruptores DIP deben
# estar en posición I²C: SW1=OFF, SW2=ON (o similar según placa)
#
# Dirección I²C del PN532: 0x24
# ============================================================

from machine import I2C, Pin
import time

PN532_I2C_ADDR   = 0x24

# Comandos PN532
CMD_GETFIRMWAREVERSION  = 0x02
CMD_SAMCONFIGURATION    = 0x14
CMD_INLISTPASSIVETARGET = 0x4A

# Tiempos de espera
TIMEOUT_MS = 1000


class PN532Error(Exception):
    pass


class PN532:

    def __init__(self, sda='P9', scl='P10'):
        """
        Inicializa el módulo PN532 en modo I²C.
        Lanza PN532Error si el módulo no responde.
        """
        self._i2c = I2C(0, mode=I2C.MASTER, pins=(sda, scl),
                        baudrate=100000)
        time.sleep_ms(100)

        # Verificar que el módulo responde
        try:
            fw = self._get_firmware_version()
            print('[NFC] PN532 detectado. FW: {}.{}'.format(fw[1], fw[2]))
        except Exception as e:
            raise PN532Error('PN532 no responde: {}'.format(e))

        # Configurar modo SAM (Single Asynchronous Mode)
        self._sam_configuration()
        print('[NFC] PN532 listo')

    def _write_cmd(self, cmd, params=None):
        """Envía un comando al PN532."""
        if params is None:
            params = []
        length  = len(params) + 2  # TFI + CMD
        tfi     = 0xD4             # Host→PN532
        checksum = (0xFF - ((tfi + cmd + sum(params)) & 0xFF)) & 0xFF

        frame = bytearray([
            0x00, 0x00, 0xFF,       # Preamble + Start code
            length & 0xFF,          # LEN
            (~length + 1) & 0xFF,   # LCS
            tfi, cmd                # TFI + CMD
        ] + list(params) + [checksum, 0x00])

        self._i2c.writeto(PN532_I2C_ADDR, frame)

    def _read_response(self, length, timeout_ms=TIMEOUT_MS):
        """Lee la respuesta del PN532."""
        t0 = time.ticks_ms()
        while time.ticks_diff(time.ticks_ms(), t0) < timeout_ms:
            try:
                # El primer byte es el indicador de estado (0x01 = listo)
                buf = self._i2c.readfrom(PN532_I2C_ADDR, length + 8)
                if buf[0] == 0x01:  # Ready
                    # Extraer datos (offset 7 = inicio de datos de respuesta)
                    return buf[7:7 + length]
            except Exception:
                pass
            time.sleep_ms(10)
        raise PN532Error('Timeout esperando respuesta')

    def _get_firmware_version(self):
        """Obtiene la versión del firmware del PN532."""
        self._write_cmd(CMD_GETFIRMWAREVERSION)
        time.sleep_ms(50)
        return self._read_response(4)

    def _sam_configuration(self):
        """Configura el módulo en modo Normal (SAM)."""
        self._write_cmd(CMD_SAMCONFIGURATION, [0x01, 0x14, 0x01])
        time.sleep_ms(50)

    def leer_uid(self, timeout_ms=500):
        """
        Intenta leer una tarjeta NFC/RFID cercana (ISO14443 tipo A).

        Retorna:
            str: UID en hexadecimal (ej. 'A1B2C3D4') si hay tarjeta
            None: si no hay tarjeta en el timeout dado
        """
        try:
            # InListPassiveTarget: 1 tarjeta, ISO14443A (0x00)
            self._write_cmd(CMD_INLISTPASSIVETARGET, [0x01, 0x00])
            time.sleep_ms(timeout_ms)

            # Leer respuesta: 20 bytes máximo
            resp = self._read_response(17)

            # resp[1] = número de tarjetas encontradas
            if len(resp) < 2 or resp[1] == 0:
                return None

            # resp[5] = longitud del UID
            uid_len = resp[5]
            if uid_len == 0 or uid_len > 7:
                return None

            # resp[6..6+uid_len] = bytes del UID
            uid_bytes = resp[6:6 + uid_len]
            uid_hex = ''.join('{:02X}'.format(b) for b in uid_bytes)
            return uid_hex

        except Exception:
            return None
