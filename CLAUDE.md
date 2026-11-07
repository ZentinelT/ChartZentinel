# ChartZentinel

Plataforma de charts propia del usuario (Zentinel). Un único archivo
`index.html` (vanilla JS + `lightweight-charts@4.2.3`), servido por
`mt5_bridge/bridge_server.py` en `http://localhost:8787/`. Repo público:
`https://github.com/ZentinelT/ChartZentinel.git`, rama `main`.

No confundir con los indicadores Pine Script "Zentinel" de otros proyectos
del usuario — esto es la app de charts en sí.

## Cómo levantarla para probar

```bash
cd /Users/arieloliva/tv-mt5-bot/ChartZentinel
python3 mt5_bridge/bridge_server.py
```

Luego abrir `http://localhost:8787/index.html` en el Browser pane (MCP).
Modo grilla multi-chart: `?layout=2` o `?layout=4`.

## Reglas de trabajo

- Responder siempre en español, con el estilo simple/directo que ya usa el
  usuario (nada de explicaciones largas salvo que las pida).
- **Antes de dar algo por terminado**, levantar el servidor y probarlo en
  vivo con el Browser pane: screenshot, consola sin errores, y el flujo
  real (no alcanza con "debería andar").
- Hacer `git commit` local después de verificar, pero **`git push` solo
  si el usuario lo pide explícitamente** (frase típica: "subí todo lo que
  falte").
- Mensajes de commit: explicar el POR QUÉ (qué reportó el usuario, qué
  causaba el bug), no solo el qué.

## Arquitectura clave (para no redescubrirla cada vez)

- **Modo grilla (`?layout=2|4`, sin `?embed=1`)**: el "shell" (documento
  externo) arma una grilla de `<iframe src="index.html?embed=1&pane=N">`
  — cada panel es una instancia completa de esta misma página. `isGridShell()`
  distingue si el código corre en el shell o dentro de un panel.
- **`paneEval(f, expr)`** (expuesto como `window._gridPaneEval`) es la
  única forma confiable de leer/escribir variables `const`/`let` de un
  panel desde el shell — `f.contentWindow.STATE` da `undefined` (los
  top-level `const` no son propiedades de `window`), pero
  `f.contentWindow.eval('STATE.symbol')` sí funciona.
- **Modales que antes "rompían" la grilla** (Settings, Trades): el patrón
  correcto es mover el modal al documento del shell (vive flotando,
  centrado, sin tocar el tamaño de ningún panel) y delegar al panel
  ACTIVO vía `paneEval` solo lo que de verdad necesita un chart real
  (`window._gridActiveFrame()` da el iframe activo). Ver
  `_sharedModalsHtml` en `renderLayoutGrid()` para el mecanismo de
  inyección del modal compartido.
- **Theme vs Workspace**: `STATE.presets` (visual: colores/márgenes/etc.)
  y `STATE.workspaces` (símbolo/TF/indicadores/dibujos) son conceptos
  separados a propósito — aplicar uno no debe tocar el otro.
- Separadores verticales de la topbar/toolbar: usar `var(--sep-color)`,
  no `var(--border)` — ese es casi invisible en modo oscuro.

## Quirks del Browser pane (MCP) al testear

- Si el tab no está "fronted", `javascript_exec` y a veces los
  screenshots pueden devolver valores/renders viejos — usar `tabs_select`
  para frontear antes de confiar en una lectura rara.
- `f.contentWindow.eval(...)` es la vía para inspeccionar estado de un
  panel de la grilla (ver `paneEval` arriba).
