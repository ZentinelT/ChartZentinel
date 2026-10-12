# Puente MT5 (Axi) → ChartZentinel

Reemplaza Twelve Data por datos reales de tu cuenta Axi en MT5. Dos piezas:

1. **`ZentinelBridge.mq5`** — un *Service* de MT5 (corre en segundo plano, sin
   necesitar un chart abierto) que escucha pedidos y devuelve velas de
   cualquier símbolo que tu broker ofrezca.
2. **`bridge_server.py`** — un servidor HTTP local (sin dependencias, solo
   Python 3) que `index.html` llama en vez de Twelve Data, y que habla con
   el Service por archivos.

## Setup (una sola vez)

1. Abrí MetaEditor (dentro de MT5: *Herramientas → MetaEditor*, o F4).
2. Copiá `ZentinelBridge.mq5` a la carpeta `MQL5/Services/` de tu instalación
   (en tu Mac: `~/Library/Application Support/net.metaquotes.wine.metatrader5/drive_c/Program Files/MetaTrader 5/MQL5/Services/`).
3. Abrilo en MetaEditor y compilalo (F7). Tiene que decir "0 errores".
4. En MT5 → panel **Navegador** → **Services** → click derecho sobre
   `ZentinelBridge` → **Start** (o arrastralo, no necesita chart).
5. Dejalo corriendo — queda activo aunque cambies de símbolo/timeframe en MT5.

## Día a día

1. Abrí MT5 y asegurate de estar logueado en tu cuenta Axi.
2. Verificá que el Service `ZentinelBridge` esté corriendo (Navegador → Services,
   ícono en verde). Si reiniciaste MT5, hay que volver a darle Start.
3. Corré el puente local:
   ```bash
   python3 mt5_bridge/bridge_server.py
   ```
   (dejalo corriendo en una terminal; podés mandarlo a background o armar un
   `launchd`/alias para no repetir el comando cada vez).
4. Abrí `index.html` en el navegador. El badge de arriba a la derecha debe
   decir **MT5 BRIDGE ✓** — si dice **BRIDGE OFF**, revisá los pasos 2 y 3.

## Cómo funciona (por si algo falla)

- `bridge_server.py` escribe un pedido en
  `Terminal/Common/Files/zentinel/request.txt` (símbolo, timeframe, cantidad
  de velas).
- El Service lo detecta (chequea cada 200ms), llama `CopyRates()` para ese
  símbolo/timeframe, y escribe la respuesta en `resp_<id>.txt` en la misma
  carpeta.
- `bridge_server.py` la lee y se la devuelve al navegador como JSON.
- Los tiempos se corrigen -7h (broker→NY) antes de salir, así las velas en
  el chart ya quedan en hora de Nueva York, sin el bug de timezone que tenía
  la versión con Twelve Data.
- `symbols.json` se regenera cada 5 minutos con **todos** los símbolos que tu
  broker ofrece (`SymbolsTotal(false)`), no solo los de tu Market Watch —
  disponible en `GET /symbols` para usar en el buscador de símbolos.

## Troubleshooting

- **"Timeout esperando a MT5"**: el Service no está corriendo, o MT5 está
  cerrado/desconectado.
- **"symbol not found"**: el símbolo no existe con ese nombre exacto en tu
  broker (ej: puede ser `NAS100` o `US100` según el broker — mirá el nombre
  exacto en el Market Watch de MT5, o pedí `GET /symbols` al puente).
- **No aparece `Common/Files/zentinel/`**: hace falta que el Service haya
  arrancado al menos una vez (crea la carpeta solo).
