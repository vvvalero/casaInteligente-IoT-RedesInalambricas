#!/usr/bin/env python3
# mqtt_simulator.py
# Simula el envío de datos de sensores via MQTT/UltraLight 2.0
# para probar el sistema sin hardware físico.
#
# Simula los 5 sensores de la casa con valores realistas y variación.
# Dependencias: pip install paho-mqtt
# Uso:          python3 mqtt_simulator.py

import paho.mqtt.client as mqtt
import time
import math
import random
import logging

logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s [%(levelname)s] %(message)s')

# ---- Configuración ----
MQTT_HOST   = "localhost"
MQTT_PORT   = 1883
APIKEY      = "smarthome-sensor-key"
INTERVALO   = 30   # segundos entre envíos (para pruebas, valor bajo)

# Sensores: device_id → habitación para logging
SENSORES = {
    "s1": "Salón",
    "s2": "Cocina",
    "s3": "Dormitorio",
    "s4": "Baño",
    "s5": "Exterior",
}

# Valores base por habitación (temperatura, humedad, luminosidad base)
VALORES_BASE = {
    "s1": {"t": 22.0, "h": 50.0, "l": 60},   # Salón
    "s2": {"t": 24.0, "h": 65.0, "l": 70},   # Cocina (más calor/humedad)
    "s3": {"t": 21.0, "h": 45.0, "l": 10},   # Dormitorio (más oscuro)
    "s4": {"t": 23.0, "h": 75.0, "l": 40},   # Baño (más humedad)
    "s5": {"t": 18.0, "h": 60.0, "l": 85},   # Exterior (más luz, menos temp)
}


def generar_lectura(sensor_id, ciclo):
    """Genera valores realistas con variación sinusoidal y ruido."""
    base = VALORES_BASE[sensor_id]
    t_offset = ciclo * 0.1

    temp = base["t"] + 3.0 * math.sin(t_offset) + random.uniform(-0.5, 0.5)
    hum  = base["h"] + 8.0 * math.sin(t_offset + 1.0) + random.uniform(-1, 1)
    lux  = base["l"] + 20 * math.sin(t_offset + 2.0) + random.uniform(-5, 5)
    pres = 1 if random.random() < 0.3 else 0   # 30% de probabilidad de presencia

    # Redondear y limitar rangos
    temp = round(max(-10, min(50, temp)), 1)
    hum  = round(max(0, min(100, hum)), 1)
    lux  = int(max(0, min(100, lux)))

    return temp, hum, lux, pres


def main():
    client = mqtt.Client(client_id="smarthome-simulator")
    client.connect(MQTT_HOST, MQTT_PORT, keepalive=60)
    client.loop_start()

    logging.info(f"Simulador conectado a {MQTT_HOST}:{MQTT_PORT}")
    logging.info(f"Enviando datos cada {INTERVALO} segundos...")
    logging.info(f"Sensores activos: {list(SENSORES.keys())}")

    ciclo = 0
    try:
        while True:
            ciclo += 1
            logging.info(f"--- Ciclo {ciclo} ---")

            for sensor_id, room_name in SENSORES.items():
                temp, hum, lux, pres = generar_lectura(sensor_id, ciclo)

                # Formato UltraLight 2.0: t|val|h|val|l|val|p|val
                payload = f"t|{temp}|h|hum|l|{lux}|p|{pres}".replace("hum", str(hum))
                topic   = f"/ul/{APIKEY}/{sensor_id}/attrs"

                result = client.publish(topic, payload, qos=1)
                logging.info(
                    f"  [{room_name}] {sensor_id} → {payload} "
                    f"(MID={result.mid})"
                )

            time.sleep(INTERVALO)

    except KeyboardInterrupt:
        logging.info("Simulador detenido.")
    finally:
        client.loop_stop()
        client.disconnect()


if __name__ == "__main__":
    main()
