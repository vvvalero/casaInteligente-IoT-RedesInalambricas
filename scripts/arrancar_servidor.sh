#!/bin/bash
# arrancar_servidor.sh — Gestiona el entorno virtual y arranca el servidor

cd "$(dirname "$0")/.." || exit 1
VENV="scripts/.venv"

echo "Casa Inteligente IoT - Servidor de notificaciones"

if [ ! -d "$VENV" ]; then
    echo "Creando entorno virtual..."
    python3 -m venv "$VENV" || {
        echo "Error. Instala: sudo apt install python3-venv python3-full"
        exit 1
    }
fi

source "$VENV/bin/activate"
pip install --quiet flask requests

if grep -q "NNSXS.XXXXXXXXXX" scripts/notification_server.py 2>/dev/null; then
    echo "AVISO: TTN_API_KEY no configurada - downlinks desactivados"
fi

echo "Servidor en http://0.0.0.0:5000"
python3 scripts/notification_server.py
