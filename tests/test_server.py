import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core import database
from core.control import ControlError
from core.server import LidiaServer, Limits, RateLimiter, TransferMeter, _parse_range


class FakeController:
    def __init__(self):
        self.calls = []

    def snapshot(self):
        return {"playing": False}

    def execute(self, command, args=None):
        if command == "bad":
            raise ControlError("orden desconocida: bad")
        self.calls.append((command, args))
        return {"playing": True}


def start(tmp_path):
    database.DB_DIR = tmp_path
    database.DB_PATH = tmp_path / "library.db"
    conn = database.init_db()
    audio = tmp_path / "a.mp3"
    audio.write_bytes(bytes(range(256)) * 4)
    conn.execute("INSERT INTO artists (name) VALUES ('Art')")
    conn.execute("INSERT INTO tracks (path, title, mtime, artist_id, duration) VALUES (?, 'Canción', 1, 1, 10)",
                 (str(audio),))
    conn.commit()
    conn.close()
    ctl = FakeController()
    server = LidiaServer(ctl, database.init_db)
    server.start()
    host, port = server.address
    return server, ctl, f"http://{host}:{port}"


def call(base, path, body=None, token=None, headers=None):
    h = dict(headers or {})
    if token:
        h["Authorization"] = f"Bearer {token}"
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(base + path, data=data, headers=h)
    try:
        with urllib.request.urlopen(req) as r:
            raw = r.read()
            return r.status, (json.loads(raw) if r.headers["Content-Type"].startswith("application/json") else raw), r.headers
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"{}"), e.headers


def test_web_page_served_without_token_on_any_non_api_path(tmp_path):
    server, ctl, base = start(tmp_path)
    try:
        for path in ("/", "/index.html", "/cualquier/ruta"):
            status, body, headers = call(base, path)
            assert status == 200 and b"id=\"pin\"" in body
            assert headers["Content-Type"].startswith("text/html")
        assert call(base, "/api/status")[0] == 401
        assert call(base, "/api/desconocida")[0] == 401
    finally:
        server.stop()


def test_auth_pairing_and_commands(tmp_path):
    server, ctl, base = start(tmp_path)
    try:
        assert call(base, "/api/ping")[0] == 200
        assert call(base, "/api/status")[0] == 401
        assert call(base, "/api/status", token="falso")[0] == 401
        assert call(base, "/api/pair", {"pin": "000000x", "name": "x"})[0] == 403
        status, data, _ = call(base, "/api/pair", {"pin": server.pairing.pin, "name": "móvil"})
        assert status == 200
        token = data["token"]
        assert call(base, "/api/status", token=token)[1] == {"playing": False}
        assert call(base, "/api/command", {"command": "next"}, token)[0] == 200
        assert ctl.calls == [("next", {})]
        assert call(base, "/api/command", {"command": "bad"}, token)[0] == 400
        assert call(base, "/api/command", {"command": "x", "args": [1]}, token)[0] == 400
        assert call(base, "/api/pair", {"pin": data["token"], "name": "x"})[0] == 403
    finally:
        server.stop()


def test_pin_rotates_after_failures(tmp_path):
    server, _, base = start(tmp_path)
    try:
        pin = server.pairing.pin
        wrong = "111111" if pin != "111111" else "222222"
        for _ in range(5):
            assert call(base, "/api/pair", {"pin": wrong})[0] == 403
        assert server.pairing.pin != pin
        assert call(base, "/api/pair", {"pin": pin})[0] == 403
    finally:
        server.stop()


def test_tracks_and_streaming(tmp_path):
    server, _, base = start(tmp_path)
    try:
        token = call(base, "/api/pair", {"pin": server.pairing.pin})[1]["token"]
        status, data, _ = call(base, "/api/tracks?q=canci", token=token)
        assert data["total"] == 1 and "path" not in data["tracks"][0]
        tid = data["tracks"][0]["id"]
        status, body, h = call(base, f"/api/tracks/{tid}/stream", token=token)
        assert status == 200 and len(body) == 1024 and h["Accept-Ranges"] == "bytes"
        status, body, h = call(base, f"/api/tracks/{tid}/stream", token=token, headers={"Range": "bytes=10-19"})
        assert status == 206 and body == bytes(range(10, 20)) and h["Content-Range"] == "bytes 10-19/1024"
        assert call(base, f"/api/tracks/{tid}/stream", token=token, headers={"Range": "bytes=5000-"})[0] == 416
        assert call(base, "/api/tracks/999/stream", token=token)[0] == 404
        assert call(base, f"/api/tracks/{tid}/stream")[0] == 401
    finally:
        server.stop()


def test_parse_range():
    assert _parse_range(None, 100) is None
    assert _parse_range("bytes=-10", 100) == (90, 99)
    assert _parse_range("bytes=50-", 100) == (50, 99)
    assert _parse_range("bytes=0-500", 100) == (0, 99)


def test_https_with_pinned_fingerprint(tmp_path):
    import hashlib
    import socket
    import ssl
    from core import tls

    cert, key = tls.ensure_certificate(tmp_path / "tls")
    assert (key.stat().st_mode & 0o077) == 0
    assert tls.ensure_certificate(tmp_path / "tls") == (cert, key)
    fp = tls.fingerprint(cert)

    database.DB_DIR = tmp_path
    database.DB_PATH = tmp_path / "library.db"
    database.init_db().close()
    server = LidiaServer(FakeController(), database.init_db, ssl_context=tls.server_context(cert, key))
    server.start()
    host, port = server.address
    try:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        with socket.create_connection((host, port), timeout=5) as raw, ctx.wrap_socket(raw) as conn:
            assert conn.version() in ("TLSv1.2", "TLSv1.3")
            seen = hashlib.sha256(conn.getpeercert(binary_form=True)).hexdigest().upper()
            assert ":".join(seen[i:i + 2] for i in range(0, len(seen), 2)) == fp
            conn.sendall(b"GET /api/ping HTTP/1.1\r\nHost: x\r\nConnection: close\r\n\r\n")
            data = b""
            while chunk := conn.recv(4096):
                data += chunk
        assert b"200 OK" in data and b'"app": "lidia"' in data

        verifying = ssl.create_default_context()
        with socket.create_connection((host, port), timeout=5) as raw:
            try:
                verifying.wrap_socket(raw, server_hostname="lidia.local")
                assert False, "debería rechazar un certificado no confiable"
            except ssl.SSLCertVerificationError:
                pass

        with socket.create_connection((host, port), timeout=5) as raw:
            raw.sendall(b"GET /api/ping HTTP/1.1\r\nHost: x\r\n\r\n")
            raw.settimeout(5)
            try:
                assert b"200 OK" not in raw.recv(4096)
            except OSError:
                pass
    finally:
        server.stop()


def _pair(server, base):
    return call(base, "/api/pair", {"pin": server.pairing.pin})[1]["token"]


def test_download_zip_and_single(tmp_path):
    import io
    import zipfile
    server, _, base = start(tmp_path)
    try:
        token = _pair(server, base)
        assert call(base, "/api/download?all=1")[0] == 401
        status, data, headers = call(base, "/api/download?all=1&token=" + token)
        assert status == 200 and headers["Content-Type"] == "application/zip"
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            assert zf.testzip() is None
            assert zf.namelist() == ["Art/Desconocido/a.mp3"]
            assert zf.read("Art/Desconocido/a.mp3") == bytes(range(256)) * 4
        status, data, headers = call(base, "/api/download?ids=1&token=" + token)
        assert status == 200 and data == bytes(range(256)) * 4
        assert "attachment" in headers["Content-Disposition"]
        assert call(base, "/api/download?ids=x&token=" + token)[0] == 400
        assert call(base, "/api/download?ids=99&token=" + token)[0] == 404
        status, data, _ = call(base, "/api/albums", token=token)
        assert status == 200 and data == {"albums": []}
    finally:
        server.stop()


def test_upload(tmp_path):
    uploaded = []
    database.DB_DIR = tmp_path
    database.DB_PATH = tmp_path / "library.db"
    database.init_db().close()
    dest = tmp_path / "up"
    server = LidiaServer(FakeController(), database.init_db, upload_dir=str(dest), on_upload=uploaded.append,
                         limits=Limits(allow_uploads=True))
    server.start()
    host, port = server.address
    base = f"http://{host}:{port}"
    try:
        token = _pair(server, base)
        def up(name, payload, tok=token):
            req = urllib.request.Request(base + "/api/upload?name=" + name, data=payload,
                                         headers={"Authorization": f"Bearer {tok}"} if tok else {})
            try:
                with urllib.request.urlopen(req) as r:
                    return r.status, json.loads(r.read())
            except urllib.error.HTTPError as e:
                return e.code, json.loads(e.read() or b"{}")
        assert up("x.mp3", b"abc", None)[0] == 401
        assert up("x.exe", b"abc")[0] == 400
        assert up("x.mp3", b"abc") == (200, {"saved": "x.mp3"})
        assert up("x.mp3", b"def") == (200, {"saved": "x (2).mp3"})
        assert up("..%2F..%2Fevil.mp3", b"z") == (200, {"saved": "evil.mp3"})
        assert (dest / "x.mp3").read_bytes() == b"abc"
        assert (dest / "evil.mp3").exists() and not (tmp_path / "evil.mp3").exists()
        assert len(uploaded) == 3
    finally:
        server.stop()


def test_rate_limiter_window():
    now = [0.0]
    rl = RateLimiter(clock=lambda: now[0])
    assert all(rl.allow("a", 3) for _ in range(3))
    assert not rl.allow("a", 3)
    assert rl.allow("b", 3)
    now[0] = 61
    assert rl.allow("a", 3)
    assert all(rl.allow("a", 0) for _ in range(50))


def test_transfer_meter_window():
    now = [0.0]
    m = TransferMeter(clock=lambda: now[0])
    m.add("a", 100)
    m.add("a", 50)
    assert m.used("a") == 150 and m.used("b") == 0
    now[0] = 86401
    assert m.used("a") == 0


def test_server_limits(tmp_path):
    server, _, base = start(tmp_path)
    try:
        token = _pair(server, base)
        server.limits.allow_uploads = False
        req = urllib.request.Request(base + "/api/upload?name=x.mp3", data=b"abc",
                                     headers={"Authorization": f"Bearer {token}"})
        try:
            urllib.request.urlopen(req)
            assert False
        except urllib.error.HTTPError as e:
            assert e.code == 403
        server.limits.allow_downloads = False
        assert call(base, "/api/download?ids=1&token=" + token)[0] == 403
        server.limits.allow_downloads = True
        server.limits.download_gb_per_day = 1
        assert call(base, "/api/download?ids=1&token=" + token)[0] == 200
        server._httpd.meter.add(next(iter(server._httpd.meter._data)), 2 * 1024 ** 3)
        assert call(base, "/api/download?ids=1&token=" + token)[0] == 429
        server._httpd.limiter = RateLimiter()
        server.limits.requests_per_minute = 2
        codes = [call(base, "/api/status", token=token)[0] for _ in range(4)]
        assert 429 in codes and codes[0] == 200
    finally:
        server.stop()


def test_upload_size_and_quota(tmp_path):
    database.DB_DIR = tmp_path
    database.DB_PATH = tmp_path / "library.db"
    database.init_db().close()
    dest = tmp_path / "up"
    server = LidiaServer(FakeController(), database.init_db, upload_dir=str(dest),
                         limits=Limits(allow_uploads=True, max_upload_mb=1, upload_quota_gb=0))
    server.start()
    host, port = server.address
    base = f"http://{host}:{port}"
    try:
        token = _pair(server, base)
        def up(payload):
            req = urllib.request.Request(base + "/api/upload?name=big.mp3", data=payload,
                                         headers={"Authorization": f"Bearer {token}"})
            try:
                return urllib.request.urlopen(req).status
            except urllib.error.HTTPError as e:
                return e.code
        assert up(b"x" * (1024 * 1024 + 1)) == 413
        assert up(b"x" * 100) == 200
    finally:
        server.stop()
