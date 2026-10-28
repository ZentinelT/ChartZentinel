#!/usr/bin/env python3
"""
Puente local HTTP <-> MT5 (via archivos) para ChartZentinel.

ChartZentinel pide velas a http://localhost:8787/ohlcv?symbol=NAS100&interval=5min&bars=500
Este servidor escribe un pedido en Common/Files/zentinel/request.txt, el Service
ZentinelBridge.mq5 (corriendo dentro de MT5) lo procesa y escribe la respuesta,
y este servidor la lee y la devuelve como JSON.

Requiere: Python 3 (sin dependencias externas), y el Service ZentinelBridge
corriendo dentro de MT5 (ver README.md en esta misma carpeta).
"""
import http.server
import json
import os
import socketserver
import threading
import time
import urllib.parse

PORT = 8787

# Carpeta de la app (la de este script es mt5_bridge/, la app está un nivel arriba).
APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATIC_MIME_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".js": "application/javascript",
    ".css": "text/css",
    ".json": "application/json",
    ".svg": "image/svg+xml",
    ".png": "image/png",
    ".ico": "image/x-icon",
}

ZENTINEL_DIR = os.path.expanduser(
    "~/Library/Application Support/net.metaquotes.wine.metatrader5/drive_c/"
    "users/user/AppData/Roaming/MetaQuotes/Terminal/Common/Files/zentinel"
)
REQUEST_FILE = os.path.join(ZENTINEL_DIR, "request.txt")

_lock = threading.Lock()


def _wait_for_response(resp_path, timeout=8.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if os.path.exists(resp_path):
            time.sleep(0.05)  # dar tiempo a que termine de escribirse
            try:
                with open(resp_path, "r", encoding="utf-8") as f:
                    content = f.read()
                os.remove(resp_path)
                return content
            except OSError:
                pass
        time.sleep(0.1)
    return None


def fetch_ohlcv(symbol, interval, bars, before=None):
    if not os.path.isdir(ZENTINEL_DIR):
        raise RuntimeError(
            "No encuentro la carpeta de MT5 (Common/Files/zentinel). "
            "¿MT5 está instalado/corrió al menos una vez?"
        )

    req_id = str(int(time.time() * 1000))
    resp_path = os.path.join(ZENTINEL_DIR, f"resp_{req_id}.txt")

    with _lock:
        tmp_path = REQUEST_FILE + ".tmp"
        with open(tmp_path, "w", encoding="utf-8") as f:
            f.write(f"id={req_id}\nsymbol={symbol}\ninterval={interval}\nbars={bars}\n")
            if before:
                f.write(f"before={before}\n")
        os.replace(tmp_path, REQUEST_FILE)

        content = _wait_for_response(resp_path)

    if content is None:
        raise RuntimeError(
            "Timeout esperando a MT5. ¿Está MT5 abierto, logueado, y el Service "
            "'ZentinelBridge' corriendo (Navegador > Services)?"
        )
    return content


# Mismo protocolo de archivos que fetch_ohlcv, pero con type=order — ver el
# bloque HandleOrderRequest() en ZentinelBridge.mq5 para las acciones
# soportadas (open/close/modify/positions/closedInfo) y sus campos.
def fetch_order(fields):
    if not os.path.isdir(ZENTINEL_DIR):
        raise RuntimeError(
            "No encuentro la carpeta de MT5 (Common/Files/zentinel). "
            "¿MT5 está instalado/corrió al menos una vez?"
        )

    req_id = str(int(time.time() * 1000))
    resp_path = os.path.join(ZENTINEL_DIR, f"resp_{req_id}.txt")

    with _lock:
        tmp_path = REQUEST_FILE + ".tmp"
        with open(tmp_path, "w", encoding="utf-8") as f:
            f.write(f"id={req_id}\ntype=order\n")
            for key, value in fields.items():
                if value is None or value == "":
                    continue
                f.write(f"{key}={value}\n")
        os.replace(tmp_path, REQUEST_FILE)

        # Una orden real puede tardar un poco más que un pedido de velas
        # (ejecución de mercado + reintentos esperando a que la posición
        # aparezca, ver HandleOrderRequest) — timeout más generoso.
        content = _wait_for_response(resp_path, timeout=15.0)

    if content is None:
        raise RuntimeError(
            "Timeout esperando a MT5. ¿Está MT5 abierto, logueado, y el Service "
            "'ZentinelBridge' corriendo (Navegador > Services)?"
        )
    return content


class Handler(http.server.BaseHTTPRequestHandler):
    def _send_json(self, status, payload_str):
        body = payload_str.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)

        if parsed.path == "/order":
            try:
                length = int(self.headers.get("Content-Length", "0"))
                raw = self.rfile.read(length) if length else b"{}"
                payload = json.loads(raw.decode("utf-8") or "{}")
            except (ValueError, json.JSONDecodeError):
                self._send_json(400, json.dumps({"error": "JSON inválido"}))
                return

            action = payload.get("action", "")
            if action not in ("open", "close", "modify", "positions", "closedInfo", "tickInfo"):
                self._send_json(400, json.dumps({"error": "action inválida: " + str(action)}))
                return

            fields = {
                "action": action,
                "symbol": payload.get("symbol", ""),
                "side": payload.get("side", ""),
                "sl": payload.get("sl", ""),
                "tp": payload.get("tp", ""),
                "ticket": payload.get("ticket", ""),
            }
            try:
                content = fetch_order(fields)
                self._send_json(200, content)
            except RuntimeError as e:
                self._send_json(502, json.dumps({"error": str(e)}))
            return

        self._send_json(404, json.dumps({"error": "not found"}))

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        qs = urllib.parse.parse_qs(parsed.query)

        if parsed.path == "/health":
            self._send_json(200, json.dumps({"ok": True}))
            return

        if parsed.path == "/symbols":
            path = os.path.join(ZENTINEL_DIR, "symbols.json")
            try:
                with open(path, "r", encoding="utf-8") as f:
                    self._send_json(200, f.read())
            except OSError:
                self._send_json(200, "[]")
            return

        if parsed.path == "/ohlcv":
            symbol = qs.get("symbol", [""])[0]
            interval = qs.get("interval", ["5min"])[0]
            bars = qs.get("bars", ["500"])[0]
            before = qs.get("before", [None])[0]
            if not symbol:
                self._send_json(400, json.dumps({"error": "falta symbol"}))
                return
            try:
                content = fetch_ohlcv(symbol, interval, bars, before)
                self._send_json(200, content)
            except RuntimeError as e:
                self._send_json(502, json.dumps({"error": str(e)}))
            return

        # Sirve la propia app (index.html y lo que haya al lado) como
        # http://localhost:PORT/ — necesario para el modo multi-chart
        # (layout=2/4): Chrome bloquea iframes file://→file://, pero no
        # http://localhost→http://localhost. Abrir http://localhost:8787/
        # en vez de doble-clickear index.html soluciona eso.
        self._send_static(parsed.path)

    def _send_static(self, url_path):
        rel_path = (url_path or "/").lstrip("/")
        if rel_path == "":
            rel_path = "index.html"
        full_path = os.path.normpath(os.path.join(APP_DIR, rel_path))
        if not full_path.startswith(APP_DIR) or not os.path.isfile(full_path):
            self._send_json(404, json.dumps({"error": "not found"}))
            return
        ext = os.path.splitext(full_path)[1]
        content_type = STATIC_MIME_TYPES.get(ext, "application/octet-stream")
        with open(full_path, "rb") as f:
            body = f.read()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        # Sin esto, una pestaña ya abierta (o un simple reload, no hard
        # refresh) puede seguir sirviendo una versión vieja de index.html
        # desde el caché del navegador después de editar el código — pasó
        # más de una vez (reportado por el usuario). App local de un solo
        # archivo, chica: no vale la pena el caching, mejor forzar siempre
        # la versión real.
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):
        print(f"[bridge] {self.address_string()} - {fmt % args}")


class ThreadingServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True


if __name__ == "__main__":
    print(f"Zentinel MT5 bridge escuchando en http://localhost:{PORT}")
    print(f"Carpeta de intercambio con MT5: {ZENTINEL_DIR}")
    ThreadingServer(("localhost", PORT), Handler).serve_forever()
