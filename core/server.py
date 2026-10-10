"""Servidor HTTP local para controlar Lidia y servir la biblioteca a otros dispositivos.

Solo biblioteca estándar. Escucha en 127.0.0.1 salvo que se indique otra dirección.
Con `ssl_context` usa HTTPS; sin él, HTTP en claro (solo para 127.0.0.1).

Autenticación: el primer dispositivo envía el PIN mostrado por la aplicación a
POST /api/pair y recibe un token; el resto de peticiones llevan `Authorization: Bearer <token>`.
"""
import hashlib
import hmac
import json
import mimetypes
import os
import secrets
import ssl
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from core.control import ControlError
from core.models import fetch_tracks

MAX_BODY = 64 * 1024
MAX_PIN_FAILURES = 5
CHUNK = 64 * 1024
HANDSHAKE_TIMEOUT = 10


class PairingStore:
    """PIN de emparejamiento y tokens (se guardan solo sus hashes en la tabla `meta`)."""

    def __init__(self, conn_factory):
        self._conn_factory = conn_factory
        self._lock = threading.Lock()
        self._failures = 0
        self.pin = self._new_pin()

    @staticmethod
    def _new_pin():
        return f"{secrets.randbelow(10**6):06d}"

    @staticmethod
    def _hash(token):
        return hashlib.sha256(token.encode()).hexdigest()

    def _load(self, conn):
        row = conn.execute("SELECT value FROM meta WHERE key = 'server_tokens'").fetchone()
        return json.loads(row[0]) if row else {}

    def _save(self, conn, tokens):
        conn.execute("INSERT INTO meta (key, value) VALUES ('server_tokens', ?) "
                     "ON CONFLICT(key) DO UPDATE SET value = excluded.value", (json.dumps(tokens),))
        conn.commit()

    def pair(self, pin, name):
        """Devuelve un token nuevo si el PIN es correcto; None en caso contrario."""
        with self._lock:
            if not isinstance(pin, str) or not hmac.compare_digest(pin, self.pin):
                self._failures += 1
                if self._failures >= MAX_PIN_FAILURES:
                    self.pin = self._new_pin()
                    self._failures = 0
                return None
            self.pin = self._new_pin()
            self._failures = 0
            token = secrets.token_urlsafe(32)
            conn = self._conn_factory()
            try:
                tokens = self._load(conn)
                tokens[self._hash(token)] = {"name": str(name)[:60], "created": int(time.time())}
                self._save(conn, tokens)
            finally:
                conn.close()
            return token

    def is_valid(self, token):
        if not token:
            return False
        conn = self._conn_factory()
        try:
            return self._hash(token) in self._load(conn)
        finally:
            conn.close()


def _parse_range(header, size):
    """Devuelve (inicio, fin) inclusivos, o None si no hay rango; lanza ValueError si es inválido."""
    if not header:
        return None
    if not header.startswith("bytes=") or "," in header:
        raise ValueError
    start, _, end = header[6:].partition("-")
    if start == "":
        length = int(end)
        if length <= 0:
            raise ValueError
        return max(0, size - length), size - 1
    first = int(start)
    last = int(end) if end else size - 1
    if first >= size or last < first:
        raise ValueError
    return first, min(last, size - 1)


class _Handler(BaseHTTPRequestHandler):
    server_version = "Lidia"
    protocol_version = "HTTP/1.1"

    def log_message(self, *args):
        pass

    # ---- utilidades
    def _send_json(self, status, payload):
        body = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _error(self, status, message):
        self._send_json(status, {"error": message})

    def _read_json(self):
        try:
            length = int(self.headers.get("Content-Length", 0))
        except ValueError:
            length = -1
        if not 0 <= length <= MAX_BODY:
            raise ValueError
        data = json.loads(self.rfile.read(length) or b"{}")
        if not isinstance(data, dict):
            raise ValueError
        return data

    def _authorized(self):
        auth = self.headers.get("Authorization", "")
        token = auth[7:] if auth.startswith("Bearer ") else ""
        if self.server.pairing.is_valid(token):
            return True
        self._error(401, "no autorizado")
        return False

    # ---- rutas
    def do_GET(self):
        url = urlparse(self.path)
        parts = [p for p in url.path.split("/") if p]
        if parts == ["api", "ping"]:
            return self._send_json(200, {"app": "lidia", "api": 1})
        if not self._authorized():
            return
        if parts == ["api", "status"]:
            return self._with_controller(self.server.controller.snapshot)
        if parts == ["api", "tracks"]:
            return self._tracks(parse_qs(url.query))
        if len(parts) == 4 and parts[:2] == ["api", "tracks"] and parts[3] in ("stream", "cover"):
            return self._file(parts[2], parts[3])
        self._error(404, "no encontrado")

    def do_POST(self):
        parts = [p for p in urlparse(self.path).path.split("/") if p]
        try:
            body = self._read_json()
        except (ValueError, UnicodeDecodeError):
            return self._error(400, "cuerpo JSON inválido")
        if parts == ["api", "pair"]:
            token = self.server.pairing.pair(body.get("pin"), body.get("name", "dispositivo"))
            if token is None:
                return self._error(403, "PIN incorrecto")
            return self._send_json(200, {"token": token})
        if not self._authorized():
            return
        if parts == ["api", "command"]:
            command = body.get("command")
            if not isinstance(command, str):
                return self._error(400, "falta command")
            args = body.get("args") or {}
            if not isinstance(args, dict):
                return self._error(400, "args debe ser un objeto")
            return self._with_controller(lambda: self.server.controller.execute(command, args))
        self._error(404, "no encontrado")

    def _with_controller(self, fn):
        try:
            self._send_json(200, fn())
        except ControlError as e:
            self._error(400, str(e))
        except Exception:
            self._error(500, "error interno")

    def _tracks(self, query):
        def num(key, default, maximum):
            try:
                return max(0, min(int(query.get(key, [default])[0]), maximum))
            except ValueError:
                return default
        limit, offset = num("limit", 100, 500), num("offset", 0, 10**7)
        conn = self.server.conn_factory()
        try:
            tracks = fetch_tracks(conn, query=query.get("q", [""])[0].strip())
        finally:
            conn.close()
        page = [{k: t[k] for k in ("id", "title", "artist", "album", "duration")}
                for t in tracks[offset:offset + limit]]
        self._send_json(200, {"total": len(tracks), "tracks": page})

    def _file(self, track_id, kind):
        try:
            track_id = int(track_id)
        except ValueError:
            return self._error(404, "no encontrado")
        conn = self.server.conn_factory()
        try:
            row = conn.execute("SELECT tracks.path, albums.cover_path FROM tracks "
                               "LEFT JOIN albums ON tracks.album_id = albums.id "
                               "WHERE tracks.id = ?", (track_id,)).fetchone()
        finally:
            conn.close()
        path = row[0 if kind == "stream" else 1] if row else None
        if not path or not os.path.isfile(path):
            return self._error(404, "no encontrado")
        size = os.path.getsize(path)
        try:
            rng = _parse_range(self.headers.get("Range"), size)
        except ValueError:
            self.send_response(416)
            self.send_header("Content-Range", f"bytes */{size}")
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        start, end = rng if rng else (0, size - 1)
        self.send_response(206 if rng else 200)
        self.send_header("Content-Type", mimetypes.guess_type(path)[0] or "application/octet-stream")
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Length", str(end - start + 1))
        if rng:
            self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        self.end_headers()
        try:
            with open(path, "rb") as f:
                f.seek(start)
                remaining = end - start + 1
                while remaining > 0:
                    chunk = f.read(min(CHUNK, remaining))
                    if not chunk:
                        break
                    self.wfile.write(chunk)
                    remaining -= len(chunk)
        except (BrokenPipeError, ConnectionResetError):
            pass


class _HTTPServer(ThreadingHTTPServer):
    ssl_context = None

    def finish_request(self, request, client_address):
        if self.ssl_context is not None:
            request.settimeout(HANDSHAKE_TIMEOUT)
            try:
                request = self.ssl_context.wrap_socket(request, server_side=True)
            except (ssl.SSLError, OSError):
                return
            request.settimeout(None)
            try:
                super().finish_request(request, client_address)
            finally:
                request.close()
            return
        super().finish_request(request, client_address)

    def handle_error(self, request, client_address):
        pass


class LidiaServer:
    def __init__(self, controller, conn_factory, host="127.0.0.1", port=0, ssl_context=None):
        self.tls = ssl_context is not None
        self.pairing = PairingStore(conn_factory)
        self._httpd = _HTTPServer((host, port), _Handler)
        self._httpd.daemon_threads = True
        self._httpd.ssl_context = ssl_context
        self._httpd.controller = controller
        self._httpd.conn_factory = conn_factory
        self._httpd.pairing = self.pairing
        self._thread = None

    @property
    def address(self):
        return self._httpd.server_address[:2]

    def start(self):
        self._thread = threading.Thread(target=self._httpd.serve_forever, name="lidia-server", daemon=True)
        self._thread.start()

    def stop(self):
        self._httpd.shutdown()
        self._httpd.server_close()
