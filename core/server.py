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
import re
import sqlite3
import threading
from collections import deque
from dataclasses import dataclass
import time
import zipfile
from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from core.control import ControlError
from core.models import fetch_tracks, fetch_tracks_by_ids
from core import sync
from core.scanner import SUPPORTED_EXTENSIONS

MAX_BODY = 64 * 1024
MAX_SYNC_BODY = 4 * 1024 * 1024
MAX_PIN_FAILURES = 5
CHUNK = 64 * 1024
HANDSHAKE_TIMEOUT = 10
MAX_UPLOAD = 100 * 1024 ** 3
MAX_DOWNLOAD_IDS = 2000


@dataclass
class Limits:
    """Límites del servidor; 0 en un tope numérico significa «sin límite»."""
    allow_downloads: bool = True
    allow_uploads: bool = False
    requests_per_minute: int = 600
    max_upload_mb: int = 1024
    upload_quota_gb: int = 20
    download_gb_per_day: int = 0


class RateLimiter:
    """Ventana deslizante de 60 s por cliente."""

    def __init__(self, clock=time.monotonic):
        self._clock = clock
        self._hits = {}
        self._lock = threading.Lock()

    def allow(self, key, limit):
        if limit <= 0:
            return True
        now = self._clock()
        with self._lock:
            hits = self._hits.setdefault(key, deque())
            while hits and now - hits[0] > 60:
                hits.popleft()
            if len(hits) >= limit:
                return False
            hits.append(now)
            if len(self._hits) > 1000:
                for k in [k for k, h in self._hits.items() if not h or now - h[-1] > 60]:
                    del self._hits[k]
            return True


class TransferMeter:
    """Bytes descargados por cliente en las últimas 24 h."""

    def __init__(self, clock=time.monotonic):
        self._clock = clock
        self._data = {}
        self._lock = threading.Lock()

    def used(self, key):
        now = self._clock()
        with self._lock:
            entries = self._data.get(key)
            if not entries:
                return 0
            while entries and now - entries[0][0] > 86400:
                entries.popleft()
            return sum(n for _, n in entries)

    def add(self, key, nbytes):
        with self._lock:
            self._data.setdefault(key, deque()).append((self._clock(), nbytes))


def _folder_size(path):
    total = 0
    for root, _, files in os.walk(path):
        for name in files:
            try:
                total += os.path.getsize(os.path.join(root, name))
            except OSError:
                pass
    return total


class _ZipSink:
    """Escribe el ZIP directamente al socket sin necesidad de poder retroceder."""

    def __init__(self, out, on_bytes=None):
        self._out = out
        self._on_bytes = on_bytes

    def write(self, data):
        self._out.write(data)
        if self._on_bytes:
            self._on_bytes(len(data))
        return len(data)

    def flush(self):
        self._out.flush()


def _safe_part(text, fallback):
    text = re.sub(r'[\\/:*?"<>|\x00-\x1f]', "_", str(text or "")).strip(" .")
    return text or fallback


def _content_disposition(filename):
    from urllib.parse import quote
    ascii_name = re.sub(r'[^A-Za-z0-9._ -]', "_", filename)
    return f"attachment; filename=\"{ascii_name}\"; filename*=UTF-8''{quote(filename)}"


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


WEB_PAGE = (Path(__file__).parent / "webui.html").read_bytes()


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
        if status in (413, 429):
            self.close_connection = True
        self._send_json(status, {"error": message})

    def _read_json(self, max_body=MAX_BODY):
        try:
            length = int(self.headers.get("Content-Length", 0))
        except ValueError:
            length = -1
        if not 0 <= length <= max_body:
            raise ValueError
        data = json.loads(self.rfile.read(length) or b"{}")
        if not isinstance(data, dict):
            raise ValueError
        return data

    def _authorized(self, allow_query=False):
        auth = self.headers.get("Authorization", "")
        token = auth[7:] if auth.startswith("Bearer ") else ""
        if not token and allow_query:
            token = parse_qs(urlparse(self.path).query).get("token", [""])[0]
        if self.server.pairing.is_valid(token):
            self._client = hashlib.sha256(token.encode()).hexdigest()
            return self._rate_ok(self._client)
        self._error(401, "no autorizado")
        return False

    def _rate_ok(self, key):
        if self.server.limiter.allow(key, self.server.limits.requests_per_minute):
            return True
        self._error(429, "demasiadas peticiones, espera un momento")
        return False

    def _download_budget_ok(self):
        cap = self.server.limits.download_gb_per_day
        if not self.server.limits.allow_downloads:
            self._error(403, "descargas desactivadas")
            return False
        if cap > 0 and self.server.meter.used(self._client) >= cap * 1024 ** 3:
            self._error(429, "límite diario de descargas alcanzado")
            return False
        return True

    def _count_download(self, nbytes):
        self.server.meter.add(self._client, nbytes)

    # ---- rutas
    def do_GET(self):
        url = urlparse(self.path)
        parts = [p for p in url.path.split("/") if p]
        if not parts or parts[0] != "api":
            body = WEB_PAGE
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if parts == ["api", "ping"]:
            return self._send_json(200, {"app": "lidia", "api": 1})
        is_file = (len(parts) == 4 and parts[:2] == ["api", "tracks"] and parts[3] in ("stream", "cover")
                   or parts == ["api", "download"])
        if not self._authorized(allow_query=is_file):
            return
        if parts == ["api", "status"]:
            return self._with_controller(self.server.controller.snapshot)
        if parts == ["api", "tracks"]:
            return self._tracks(parse_qs(url.query))
        if parts == ["api", "sync"]:
            return self._sync_pull(parse_qs(url.query))
        if parts == ["api", "albums"]:
            return self._albums()
        if parts == ["api", "download"]:
            return self._download(parse_qs(url.query))
        if len(parts) == 4 and parts[:2] == ["api", "tracks"] and parts[3] in ("stream", "cover"):
            return self._file(parts[2], parts[3])
        self._error(404, "no encontrado")

    def do_POST(self):
        url = urlparse(self.path)
        parts = [p for p in url.path.split("/") if p]
        if parts == ["api", "upload"]:
            if not self._authorized():
                return
            return self._upload(parse_qs(url.query))
        try:
            body = self._read_json(MAX_SYNC_BODY if parts == ["api", "sync"] else MAX_BODY)
        except (ValueError, UnicodeDecodeError):
            return self._error(400, "cuerpo JSON inválido")
        if parts == ["api", "pair"]:
            if not self._rate_ok("ip:" + self.client_address[0]):
                return
            token = self.server.pairing.pair(body.get("pin"), body.get("name", "dispositivo"))
            if token is None:
                return self._error(403, "PIN incorrecto")
            return self._send_json(200, {"token": token})
        if not self._authorized():
            return
        if parts == ["api", "sync"]:
            return self._sync_push(body)
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
        album_id = None
        if "album_id" in query:
            try:
                album_id = int(query["album_id"][0])
            except ValueError:
                return self._error(400, "album_id inválido")
        conn = self.server.conn_factory()
        try:
            tracks = fetch_tracks(conn, query=query.get("q", [""])[0].strip(), album_id=album_id)
        finally:
            conn.close()
        page = [{k: t[k] for k in ("id", "uid", "title", "artist", "album", "duration")}
                for t in tracks[offset:offset + limit]]
        self._send_json(200, {"total": len(tracks), "tracks": page})

    def _sync_pull(self, query):
        since = query.get("since", [""])[0]
        if since and not sync._TS.match(since):
            return self._error(400, "since inválido")
        conn = self.server.conn_factory()
        try:
            self._send_json(200, sync.export_changes(conn, since))
        finally:
            conn.close()

    def _sync_push(self, body):
        conn = self.server.conn_factory()
        try:
            result = sync.apply_changes(conn, body)
        except sqlite3.Error:
            return self._error(500, "error interno")
        finally:
            conn.close()
        if self.server.on_sync:
            self.server.on_sync()
        self._send_json(200, result)

    def _albums(self):
        conn = self.server.conn_factory()
        try:
            rows = conn.execute("""
                SELECT albums.id, albums.title, artists.name, COUNT(tracks.id)
                FROM albums
                LEFT JOIN artists ON albums.artist_id = artists.id
                JOIN tracks ON tracks.album_id = albums.id
                GROUP BY albums.id
                ORDER BY LOWER(albums.title)""").fetchall()
        finally:
            conn.close()
        self._send_json(200, {"albums": [
            {"id": r[0], "title": r[1], "artist": r[2], "tracks": r[3]} for r in rows]})

    def _download(self, query):
        if not self._download_budget_ok():
            return
        conn = self.server.conn_factory()
        try:
            if query.get("all", [""])[0] == "1":
                tracks = fetch_tracks(conn)
                name = "Lidia - biblioteca"
            elif "album" in query:
                try:
                    album_id = int(query["album"][0])
                except ValueError:
                    return self._error(400, "album inválido")
                tracks = fetch_tracks(conn, album_id=album_id)
                name = _safe_part(tracks[0]["album"], "album") if tracks else "album"
            elif "ids" in query:
                try:
                    ids = [int(i) for i in query["ids"][0].split(",") if i]
                except ValueError:
                    return self._error(400, "ids inválidos")
                if not ids or len(ids) > MAX_DOWNLOAD_IDS:
                    return self._error(400, f"ids: de 1 a {MAX_DOWNLOAD_IDS}")
                tracks = fetch_tracks_by_ids(conn, ids)
                name = "Lidia - selección"
            else:
                return self._error(400, "falta all, album o ids")
        finally:
            conn.close()
        tracks = [t for t in tracks if t["path"] and os.path.isfile(t["path"])]
        if not tracks:
            return self._error(404, "no encontrado")
        if len(tracks) == 1 and "ids" in query:
            return self._send_file(tracks[0]["path"], download=True)
        self.send_response(200)
        self.send_header("Content-Type", "application/zip")
        self.send_header("Content-Disposition", _content_disposition(name + ".zip"))
        self.send_header("Connection", "close")
        self.end_headers()
        self.close_connection = True
        used = set()
        try:
            with zipfile.ZipFile(_ZipSink(self.wfile, self._count_download), "w", zipfile.ZIP_STORED, allowZip64=True) as zf:
                for t in tracks:
                    base = os.path.basename(t["path"])
                    arc = "/".join((_safe_part(t["artist"], "Desconocido"),
                                    _safe_part(t["album"], "Desconocido"), _safe_part(base, "pista")))
                    stem, ext = os.path.splitext(arc)
                    n = 1
                    while arc in used:
                        n += 1
                        arc = f"{stem} ({n}){ext}"
                    used.add(arc)
                    info = zipfile.ZipInfo.from_file(t["path"], arc)
                    info.compress_type = zipfile.ZIP_STORED
                    with open(t["path"], "rb") as src, zf.open(info, "w", force_zip64=True) as dst:
                        while chunk := src.read(CHUNK):
                            dst.write(chunk)
        except (BrokenPipeError, ConnectionResetError, OSError):
            pass

    def _upload(self, query):
        upload_dir = self.server.upload_dir
        limits = self.server.limits
        if not upload_dir or not limits.allow_uploads:
            self.close_connection = True
            return self._error(403, "subidas desactivadas")
        raw = query.get("name", [""])[0]
        name = _safe_part(os.path.basename(raw.replace("\\", "/")), "")
        if os.path.splitext(name)[1].lower() not in SUPPORTED_EXTENSIONS:
            self.close_connection = True
            return self._error(400, "formato no admitido")
        try:
            length = int(self.headers.get("Content-Length", ""))
        except ValueError:
            self.close_connection = True
            return self._error(411, "falta Content-Length")
        max_bytes = limits.max_upload_mb * 1024 * 1024 if limits.max_upload_mb > 0 else MAX_UPLOAD
        if not 0 < length <= max_bytes:
            return self._error(413, "tamaño no permitido")
        os.makedirs(upload_dir, exist_ok=True)
        quota = limits.upload_quota_gb * 1024 ** 3
        if quota > 0 and _folder_size(upload_dir) + length > quota:
            return self._error(413, "cuota de subidas agotada")
        stem, ext = os.path.splitext(name)
        target, n = os.path.join(upload_dir, name), 1
        while True:
            try:
                f = open(target, "xb")
                break
            except FileExistsError:
                n += 1
                target = os.path.join(upload_dir, f"{stem} ({n}){ext}")
        remaining, ok = length, False
        try:
            with f:
                while remaining > 0:
                    chunk = self.rfile.read(min(CHUNK, remaining))
                    if not chunk:
                        break
                    f.write(chunk)
                    remaining -= len(chunk)
            ok = remaining == 0
        finally:
            if not ok:
                self.close_connection = True
                try:
                    os.remove(target)
                except OSError:
                    pass
        if not ok:
            return
        if self.server.on_upload:
            self.server.on_upload(target)
        self._send_json(200, {"saved": os.path.basename(target)})

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
        download = kind == "stream" and parse_qs(urlparse(self.path).query).get("download") == ["1"]
        if download and not self._download_budget_ok():
            return
        self._send_file(path, download=download)

    def _send_file(self, path, download=False):
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
        if download:
            self.send_header("Content-Disposition", _content_disposition(os.path.basename(path)))
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
                    if download:
                        self._count_download(len(chunk))
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
    def __init__(self, controller, conn_factory, host="127.0.0.1", port=0, ssl_context=None,
                 upload_dir=None, on_upload=None, limits=None, on_sync=None):
        self.tls = ssl_context is not None
        self.pairing = PairingStore(conn_factory)
        self._httpd = _HTTPServer((host, port), _Handler)
        self._httpd.daemon_threads = True
        self._httpd.ssl_context = ssl_context
        self._httpd.controller = controller
        self._httpd.conn_factory = conn_factory
        self._httpd.pairing = self.pairing
        self.limits = limits or Limits()
        self._httpd.limits = self.limits
        self._httpd.limiter = RateLimiter()
        self._httpd.meter = TransferMeter()
        self._httpd.upload_dir = upload_dir
        self._httpd.on_upload = on_upload
        self._httpd.on_sync = on_sync
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
