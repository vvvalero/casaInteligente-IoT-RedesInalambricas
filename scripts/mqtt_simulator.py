#!/usr/bin/env python3
# mqtt_simulator.py
# Simula el envío de datos de sensores via MQTT/UltraLight 2.0
# para probar el sistema sin hardware físico.
#
# Simula los 3 nodos de la casa con valores realistas y variación.
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
    "s2": "Dormitorio",
    "s3": "Exterior",
}

# Valores base por habitación
VALORES_BASE = {
    "s1": {"t": 22.0, "h": 50.0, "l": 60, "p": 1013.2, "acc": 1.0},
    "s2": {"t": 21.0, "h": 45.0, "l": 10, "nfc": True},
    "s3": {"t": 18.0, "h": 60.0, "p": 1010.5, "ble": 2},
}


def generar_lectura(sensor_id, ciclo):
    """Genera valores realistas adaptados al sensor actual y añade ruido.
       Usa las claves exactas (object_id) configuradas en el IoT Agent.
    """
    base = VALORES_BASE[sensor_id]
    t_offset = ciclo * 0.1

    temp = base["t"] + 3.0 * math.sin(t_offset) + random.uniform(-0.5, 0.5)
    hum  = base["h"] + 8.0 * math.sin(t_offset + 1.0) + random.uniform(-1, 1)

    # Redondear temp y hum
    temp = round(max(-10, min(50, temp)), 1)
    hum  = round(max(0, min(100, hum)), 1)
    
    lectura = {"temperature": temp, "humidity": hum}
    
    # Valores extra por sensor
    if "l" in base:
        lux = base["l"] + 20 * math.sin(t_offset + 2.0) + random.uniform(-5, 5)
        lectura["luminosity"] = int(max(0, min(200, lux)))
    
    if "p" in base:
        pres = base["p"] + 2.0 * math.cos(t_offset) + random.uniform(-1, 1)
        lectura["barometricPressure"] = round(pres, 1)
        
    if "acc" in base:
        lectura["accelerationMagnitude"] = round(base["acc"] + random.uniform(-0.1, 0.1), 3)
        
    if "ble" in base:
        # Simular aforo exterior
        ble_devs = int(base["ble"] + random.randint(-1, 2) + 2*math.sin(t_offset))
        lectura["bleDevicesNearby"] = max(0, ble_devs)
        
    if "nfc" in base:
        # Simular lectura NFC ocasional o estado esperando
        if random.random() < 0.3:
            lectura["nfcDetected"] = 1
        else:
            lectura["nfcDetected"] = 0

    return lectura


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
                lectura = generar_lectura(sensor_id, ciclo)

                # Construir string formato UltraLight 2.0 (ej: temperature|22.1|humidity|50.4)
                parts = []
                for k, v in lectura.items():
                    parts.extend([k, str(v)])
                payload = "|".join(parts)
                
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
