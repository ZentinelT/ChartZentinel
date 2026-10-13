#!/bin/bash
# Doble clic para arrancar ChartZentinel: prende el puente MT5 (si no está
# corriendo ya) y abre la app en Chrome por http://localhost:8787/ — la
# única forma de abrirla ahora, sirve igual para 1, 2 o 4 gráficos.
cd "/Users/arieloliva/tv-mt5-bot/ChartZentinel"

URL="http://localhost:8787/"

if curl -s -o /dev/null -m 1 "${URL}health"; then
  echo "El puente ya está corriendo, abriendo el navegador…"
  open "$URL"
else
  echo "Arrancando el puente MT5…"
  nohup python3 mt5_bridge/bridge_server.py > /tmp/zentinel_bridge.log 2>&1 &
  for i in 1 2 3 4 5 6 7 8 9 10; do
    sleep 0.5
    if curl -s -o /dev/null -m 1 "${URL}health"; then
      break
    fi
  done
  open "$URL"
fi
