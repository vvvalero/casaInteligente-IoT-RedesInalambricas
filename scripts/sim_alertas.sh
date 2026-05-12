#!/usr/bin/env bash
# sim_alertas.sh — Simulador de alertas para test del pipeline IoT
# Uso: ./sim_alertas.sh [URL_servidor]
# Ejemplo: ./sim_alertas.sh http://localhost:5000

SERVER="${1:-https://api.vvalero.dev}"

RED='\033[0;31m'; GRN='\033[0;32m'; YLW='\033[1;33m'
BLU='\033[0;34m'; CYN='\033[0;36m'; BLD='\033[1m'; RST='\033[0m'

uplink() {
    local device="$1"; shift
    local payload="$1"
    local resp
    resp=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$SERVER/iot/ul" \
        -H "Content-Type: application/json" \
        -d "{\"end_device_ids\":{\"device_id\":\"$device\"},\"uplink_message\":{\"decoded_payload\":$payload}}")
    if [ "$resp" = "200" ]; then
        echo -e "  ${GRN}OK${RST} → $device  $payload"
    else
        echo -e "  ${RED}ERROR $resp${RST} → $device  $payload"
    fi
}

header() {
    echo -e "\n${BLD}${CYN}=== $1 ===${RST}"
}

# Repite el uplink cada $REPEAT_INTERVAL segundos durante $REPEAT_DURATION segundos.
# Necesario porque el LoPy4 real sobreescribe el estado simulado en cada uplink real.
# El LoPy4-dormitorio puede tardar hasta TX_INTERVAL (~60 s) en hacer TX y recibir el downlink.
REPEAT_INTERVAL=10
REPEAT_DURATION=90

persist() {
    local device="$1"
    local payload="$2"
    local label="$3"
    local end=$((SECONDS + REPEAT_DURATION))
    echo -e "  ${YLW}Modo persistente: enviando cada ${REPEAT_INTERVAL}s durante ${REPEAT_DURATION}s${RST}"
    echo -e "  ${YLW}(el LoPy4-dormitorio debe hacer TX para recibir el downlink)${RST}"
    while [ $SECONDS -lt $end ]; do
        uplink "$device" "$payload"
        local restante=$((end - SECONDS))
        printf "  Quedan %ds — Ctrl+C para cancelar\r" "$restante"
        sleep $REPEAT_INTERVAL
    done
    echo -e "\n  ${GRN}Fin del modo persistente.${RST}"
}

status() {
    echo -e "\n${BLD}Estado actual de alertas:${RST}"
    curl -s "$SERVER/api/alertas" | python3 -m json.tool 2>/dev/null || \
        curl -s "$SERVER/api/alertas"
    echo
}

menu() {
    echo -e "\n${BLD}${BLU}╔══════════════════════════════════════╗${RST}"
    echo -e "${BLD}${BLU}║   Simulador de Alertas — Casa IoT   ║${RST}"
    echo -e "${BLD}${BLU}╚══════════════════════════════════════╝${RST}"
    echo -e "  Servidor: ${CYN}$SERVER${RST}\n"
    echo -e " ${BLD}── Temperatura ────────────────────────${RST}"
    echo -e "  ${YLW}1${RST}  Temp alta (>28°C) en s1 Salón"
    echo -e "  ${YLW}2${RST}  Temp alta (>28°C) en s2 Dormitorio"
    echo -e "  ${YLW}3${RST}  Temp alta (>28°C) en s3 Exterior"
    echo -e "  ${YLW}4${RST}  Temp alta en s1 + s2  → Indicador 4 AMARILLO"
    echo -e "  ${YLW}5${RST}  Temp baja (<10°C) en s3 Exterior"
    echo -e "  ${BLU}p${RST}  ${BLU}Persistente: repite s1 temp alta cada 10 s durante 90 s${RST}"
    echo -e ""
    echo -e " ${BLD}── Humedad ─────────────────────────────${RST}"
    echo -e "  ${YLW}6${RST}  Humedad alta (>80%) en s1 Salón"
    echo -e "  ${YLW}7${RST}  Humedad alta en s1 + s2  → Indicador 5 AMARILLO"
    echo -e ""
    echo -e " ${BLD}── Combinado ───────────────────────────${RST}"
    echo -e "  ${YLW}8${RST}  Todo mal: temp+humedad en los 3 nodos"
    echo -e "  ${YLW}9${RST}  Vibración detectada en s1"
    echo -e "  ${YLW}a${RST}  Lux baja (exterior)"
    echo -e "  ${YLW}b${RST}  Aforo superado en s2"
    echo -e ""
    echo -e " ${BLD}── Reset ───────────────────────────────${RST}"
    echo -e "  ${YLW}r${RST}  ${GRN}Reset: todo normal (todos los nodos OK)${RST}"
    echo -e ""
    echo -e " ${BLD}── Info ────────────────────────────────${RST}"
    echo -e "  ${YLW}s${RST}  Ver alertas activas en Orion"
    echo -e "  ${YLW}q${RST}  Salir"
    echo -e ""
    printf "  Opción: "
}

run_option() {
    case "$1" in
        1)
            header "Temp alta en s1 (Salón)"
            uplink "lopy4-salon" '{"temperature":35,"humidity":50}'
            echo -e "  ${RED}→ Indicador 1 ROJO + Indicador 4 NARANJA${RST}"
            ;;
        2)
            header "Temp alta en s2 (Dormitorio)"
            uplink "lopy4-dormitorio" '{"temperature":35,"humidity":50}'
            echo -e "  ${RED}→ Indicador 2 ROJO + Indicador 4 NARANJA${RST}"
            ;;
        3)
            header "Temp alta en s3 (Exterior)"
            uplink "lopy4-exterior" '{"temperature":35,"humidity":50}'
            echo -e "  ${RED}→ Indicador 3 ROJO + Indicador 4 NARANJA${RST}"
            ;;
        4)
            header "Temp alta en s1 + s2 → crítico"
            uplink "lopy4-salon"      '{"temperature":35,"humidity":50}'
            uplink "lopy4-dormitorio" '{"temperature":35,"humidity":50}'
            echo -e "  ${YLW}→ Indicadores 1+2 ROJOS + Indicador 4 AMARILLO (crítico)${RST}"
            ;;
        5)
            header "Temp baja en s3 (Exterior)"
            uplink "lopy4-exterior" '{"temperature":5,"humidity":50}'
            echo -e "  ${BLU}→ Indicador 3 ROJO + Indicador 4 NARANJA${RST}"
            ;;
        p|P)
            header "Persistente: s1 temp alta (90 s)"
            echo -e "  ${YLW}Motivo: el LoPy4 real sobreescribe el simulado en cada uplink.${RST}"
            echo -e "  ${YLW}Este modo mantiene la alerta viva hasta que el LoPy4-dormitorio${RST}"
            echo -e "  ${YLW}haga TX y reciba el downlink 0x0A con el estado de alerta.${RST}\n"
            persist "lopy4-salon" '{"temperature":35,"humidity":50}' "s1 temp alta"
            echo -e "  ${RED}→ Indicador 1 ROJO + Indicador 4 NARANJA${RST}"
            ;;
        6)
            header "Humedad alta en s1 (Salón)"
            uplink "lopy4-salon" '{"temperature":20,"humidity":90}'
            echo -e "  ${RED}→ Indicador 1 ROJO + Indicador 5 NARANJA${RST}"
            ;;
        7)
            header "Humedad alta en s1 + s2 → crítico"
            uplink "lopy4-salon"      '{"temperature":20,"humidity":90}'
            uplink "lopy4-dormitorio" '{"temperature":20,"humidity":90}'
            echo -e "  ${YLW}→ Indicadores 1+2 ROJOS + Indicador 5 AMARILLO (crítico)${RST}"
            ;;
        8)
            header "Todo mal: temp+humedad en los 3 nodos"
            uplink "lopy4-salon"      '{"temperature":35,"humidity":90}'
            uplink "lopy4-dormitorio" '{"temperature":35,"humidity":90}'
            uplink "lopy4-exterior"   '{"temperature":35,"humidity":90}'
            echo -e "  ${RED}→ Indicadores 1-3 ROJOS + 4 AMARILLO + 5 AMARILLO${RST}"
            ;;
        9)
            header "Vibración en s1 (Salón)"
            uplink "lopy4-salon" '{"temperature":20,"humidity":50,"vibrationDetected":true,"accelerationMagnitude":2.5}'
            echo -e "  ${RED}→ Indicador 1 ROJO + downlink LED RGB LoPy4${RST}"
            ;;
        a|A)
            header "Lux baja en Exterior"
            uplink "lopy4-exterior" '{"temperature":20,"humidity":50,"luminosity":10}'
            echo -e "  ${YLW}→ Downlink lux_low al LoPy4 exterior${RST}"
            ;;
        b|B)
            header "Aforo superado en Dormitorio"
            uplink "lopy4-dormitorio" '{"temperature":20,"humidity":50,"bleDevicesNearby":8}'
            echo -e "  ${YLW}→ Downlink aforo al LoPy4 dormitorio${RST}"
            ;;
        r|R)
            header "Reset: todo normal"
            uplink "lopy4-salon"      '{"temperature":20,"humidity":50,"vibrationDetected":false,"accelerationMagnitude":0,"bleDevicesNearby":0}'
            uplink "lopy4-dormitorio" '{"temperature":20,"humidity":50,"bleDevicesNearby":0}'
            uplink "lopy4-exterior"   '{"temperature":20,"humidity":50,"luminosity":200}'
            echo -e "  ${GRN}→ Todos los indicadores VERDE/AZUL (OK)${RST}"
            ;;
        s|S)
            status
            ;;
        q|Q)
            echo -e "\n${GRN}Saliendo.${RST}\n"
            exit 0
            ;;
        *)
            echo -e "  ${RED}Opción no válida.${RST}"
            ;;
    esac
}

# Modo no interactivo: ./sim_alertas.sh [url] <opción>
if [ -n "$2" ]; then
    run_option "$2"
    exit 0
fi

# Modo interactivo
while true; do
    menu
    read -r opt
    run_option "$opt"
done
