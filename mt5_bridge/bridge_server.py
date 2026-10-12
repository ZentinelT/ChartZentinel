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
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.end_headers()

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

        self._send_json(404, json.dumps({"error": "not found"}))

    def log_message(self, fmt, *args):
        print(f"[bridge] {self.address_string()} - {fmt % args}")


class ThreadingServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True


if __name__ == "__main__":
    print(f"Zentinel MT5 bridge escuchando en http://localhost:{PORT}")
    print(f"Carpeta de intercambio con MT5: {ZENTINEL_DIR}")
    ThreadingServer(("localhost", PORT), Handler).serve_forever()
