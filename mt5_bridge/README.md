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

## Trading real (abrir/cerrar/modificar en tu cuenta de MT5)

Además de leer velas, el Service ahora también puede mandar órdenes reales
a la cuenta que tengas logueada en esa instancia de MT5 — desde el toggle
**"Real trading (MT5)"** en el modal de Trades de ChartZentinel.

**Importante antes de usarlo:**

- **Probalo primero en una cuenta DEMO**, no en la real, hasta confirmar que
  abre/cierra/modifica bien.
- El **volumen (lotaje) lo decide MT5, no la app** — a propósito. Después de
  recompilar, en MT5 → Navegador → Services → click derecho sobre
  `ZentinelBridge` → **Properties**, ajustá el input `DefaultVolume` al
  tamaño que quieras usar. Todas las operaciones que abras desde
  ChartZentinel van a usar ESE volumen, siempre.
- Tenés que tener el **"Algo Trading"** (el botón grande de la barra de
  herramientas de MT5) **prendido** — si está apagado, cualquier orden se
  rechaza, igual que con un Expert Advisor.
- Después de actualizar `ZentinelBridge.mq5`, hay que **recompilarlo**
  (MetaEditor, F7) y reiniciar el Service (Stop → Start) para que tome los
  cambios.
- El toggle **arranca apagado siempre** que abrís o recargás la app — no
  queda prendido solo. Mientras está apagado, todo sigue funcionando como
  papel-trading (simulado), igual que antes.
- Las operaciones que abre ChartZentinel quedan etiquetadas con un magic
  number propio — nunca lista ni toca operaciones que hayas abierto a mano
  directo en MT5.

## Troubleshooting

- **"Timeout esperando a MT5"**: el Service no está corriendo, o MT5 está
  cerrado/desconectado.
- **"symbol not found"**: el símbolo no existe con ese nombre exacto en tu
  broker (ej: puede ser `NAS100` o `US100` según el broker — mirá el nombre
  exacto en el Market Watch de MT5, o pedí `GET /symbols` al puente).
- **No aparece `Common/Files/zentinel/`**: hace falta que el Service haya
  arrancado al menos una vez (crea la carpeta solo).
