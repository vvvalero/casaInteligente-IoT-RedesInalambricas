#!/bin/bash
# setup_dmz.sh — Configuración inicial del servidor DMZ
# Dominio: api.vvalero.dev
# ============================================================
# Ejecutar UNA SOLA VEZ en la VM del DMZ tras clonar el repo.
#
# Prerrequisitos en la VM:
#   - Ubuntu Server 22.04 o 24.04
#   - Docker Engine instalado
#   - Puerto 80 y 443 accesibles desde internet
#   - Registro DNS tipo A: api.vvalero.dev → IP pública de la VM
#     (configurar en Vercel → Domains → vvalero.dev → DNS Records)
#
# Uso:
#   bash scripts/setup_dmz.sh
# ============================================================

set -e

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; NC='\033[0m'
ok()   { echo -e "${GREEN}✓${NC} $1"; }
warn() { echo -e "${YELLOW}⚠${NC}  $1"; }
err()  { echo -e "${RED}✗${NC} $1"; exit 1; }

echo "=================================================="
echo "  Casa Inteligente IoT — Setup DMZ"
echo "  Dominio: api.vvalero.dev"
echo "=================================================="
echo ""

[ ! -f "docker/docker-compose_dmz.yml" ] && err "Ejecuta desde la raíz del proyecto"

# ---- Leer .env o pedirlo ----
if [ -f ".env" ]; then
    set -a; source .env; set +a
    ok "Fichero .env encontrado (dominio: ${DOMAIN:-api.vvalero.dev})"
else
    warn "Fichero .env no encontrado — usando valores por defecto"
    cp .env.example .env

    echo ""
    echo "Rellena las credenciales TTN:"
    read -p "  TTN API Key (NNSXS...): " TTN_API_KEY_INPUT
    read -p "  Device ID nodo salón en TTN [lopy4-salon]: " S1
    read -p "  Device ID nodo dormitorio en TTN [lopy4-dormitorio]: " S2
    read -p "  Device ID nodo exterior en TTN [lopy4-exterior]: " S3

    sed -i "s|NNSXS.TU_API_KEY_AQUI|${TTN_API_KEY_INPUT}|" .env
    [ -n "$S1" ] && sed -i "s|lopy4-salon|${S1}|" .env
    [ -n "$S2" ] && sed -i "s|lopy4-dormitorio|${S2}|" .env
    [ -n "$S3" ] && sed -i "s|lopy4-exterior|${S3}|" .env

    set -a; source .env; set +a
    ok "Fichero .env configurado"
fi

DOMAIN="${DOMAIN:-api.vvalero.dev}"

echo ""
echo "--- [1/5] Verificando Docker ---"
docker --version > /dev/null 2>&1 || err "Docker no instalado. Instalar con: curl -fsSL https://get.docker.com | sh"
docker compose version > /dev/null 2>&1 || err "Docker Compose no disponible"
ok "Docker OK"

echo ""
echo "--- [2/5] Verificando DNS ---"
echo "  Comprobando que $DOMAIN apunta a esta máquina..."
IP_DNS=$(dig +short $DOMAIN 2>/dev/null | tail -1)
IP_LOCAL=$(curl -s --max-time 5 ifconfig.me 2>/dev/null || curl -s --max-time 5 icanhazip.com 2>/dev/null)

if [ "$IP_DNS" = "$IP_LOCAL" ]; then
    ok "DNS OK: $DOMAIN → $IP_LOCAL"
else
    warn "DNS no coincide:"
    warn "  $DOMAIN resuelve a: ${IP_DNS:-'(sin resolución)'}"
    warn "  IP pública de esta VM: ${IP_LOCAL:-'(no detectada)'}"
    warn ""
    warn "En Vercel → Domains → vvalero.dev → DNS Records, añade:"
    warn "  Tipo: A  |  Nombre: api  |  Valor: ${IP_LOCAL:-IP_DE_LA_VM}"
    echo ""
    read -p "  ¿Continuar de todas formas? (s/N): " CONT
    [[ "$CONT" != "s" && "$CONT" != "S" ]] && exit 1
fi

echo ""
echo "--- [3/5] Arrancando Nginx en HTTP para validación Let's Encrypt ---"
# Nginx no puede arrancar con la config HTTPS si el certificado aún no existe.
# Usamos config temporal HTTP-only para la validación ACME.
NGINX_CONF="docker/nginx/conf.d/smarthome.conf"
cp "$NGINX_CONF" "${NGINX_CONF}.bak"
cat > "$NGINX_CONF" << 'NGINXEOF'
server {
    listen 80;
    server_name _;
    location /.well-known/acme-challenge/ {
        root /var/www/certbot;
    }
    location / {
        return 200 "ok\n";
        add_header Content-Type text/plain;
    }
}
NGINXEOF
docker compose -f docker/docker-compose_dmz.yml up -d nginx
sleep 5
ok "Nginx arrancado (modo HTTP temporal)"

echo ""
echo "--- [4/5] Obteniendo certificado TLS para $DOMAIN ---"
docker run --rm \
    -v "$(pwd)/docker/certbot-www:/var/www/certbot" \
    -v "$(pwd)/docker/certbot-certs:/etc/letsencrypt" \
    certbot/certbot certonly \
    --webroot \
    --webroot-path /var/www/certbot \
    --email valen@vvalero.dev \
    --agree-tos \
    --no-eff-email \
    --non-interactive \
    -d $DOMAIN

ok "Certificado TLS obtenido para $DOMAIN"

# Restaurar configuración HTTPS completa
cp "${NGINX_CONF}.bak" "$NGINX_CONF"
rm "${NGINX_CONF}.bak"
ok "Configuración Nginx HTTPS restaurada"

echo ""
echo "--- [5/5] Arrancando stack completo ---"
docker compose -f docker/docker-compose_dmz.yml up -d
echo "Esperando a que los servicios estén listos..."
sleep 25
docker exec smarthome-nginx nginx -s reload
ok "Nginx recargado con configuración HTTPS"

echo ""
echo "Verificando servicios:"
echo -n "  Nginx HTTPS:        "
curl -s -o /dev/null -w "HTTP %{http_code}\n" https://$DOMAIN/health 2>/dev/null || echo "No responde"

echo -n "  Orion:              "
docker exec smarthome-orion curl -s http://localhost:1026/version 2>/dev/null \
    | python3 -c "import sys,json; d=json.load(sys.stdin); print('OK v'+d['orion']['version'])" \
    2>/dev/null || echo "No disponible"

echo -n "  IoT Agent:          "
docker exec smarthome-iot-agent curl -s http://localhost:4041/iot/about > /dev/null 2>&1 \
    && echo "OK" || echo "No disponible"

echo -n "  Notification server:"
docker exec smarthome-notification curl -s http://localhost:5000/health > /dev/null 2>&1 \
    && echo "OK" || echo "No disponible"

echo ""
echo "=================================================="
ok "Setup completado"
echo ""
echo "  Webhook TTN Console:"
echo "  → https://$DOMAIN/iot/ul"
echo ""
echo "  Endpoints API:"
echo "  → https://$DOMAIN/health"
echo "  → https://$DOMAIN/api/alerts"
echo "  → https://$DOMAIN/api/access-log"
echo ""
echo "  Próximos pasos:"
echo "  1. bash fiware/ngsi/ngsi_crear_entidades.sh"
echo "  2. bash fiware/iot-agent/iot_agent_setup.sh"
echo "  3. bash fiware/subscriptions/ngsi_subscripciones.sh"
echo "  4. Configurar webhook en TTN → https://$DOMAIN/iot/ul"
echo "=================================================="
