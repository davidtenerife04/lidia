import os
import sys
import wave
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core import database, scanner
from core.scanner import scan_directory


def make_db(tmp_path):
    database.DB_DIR = tmp_path
    database.DB_PATH = tmp_path / "library.db"
    return database.init_db()


def write_wav(path, seconds=1):
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(8000)
        w.writeframes(b"\x00\x00" * 8000 * seconds)


def titles(conn):
    return [r[0] for r in conn.execute("SELECT title FROM tracks ORDER BY title")]


def test_scan_indexes_audio_and_ignores_others(tmp_path):
    conn = make_db(tmp_path / "db")
    music = tmp_path / "music"
    write_wav(music / "Album" / "uno.wav", 2)
    write_wav(music / "Album" / "dos.wav")
    (music / "Album" / "notas.txt").write_text("no es audio")
    total = scan_directory(str(music), conn)
    assert total == 2
    assert titles(conn) == ["dos", "uno"]
    row = conn.execute("SELECT duration FROM tracks WHERE title = 'uno'").fetchone()
    assert row[0] == 2
    album = conn.execute("SELECT title FROM albums").fetchone()
    assert album[0] == "Album"
    assert conn.execute("SELECT name FROM artists").fetchone()[0] == scanner.UNKNOWN


def test_scan_is_incremental(tmp_path, monkeypatch):
    conn = make_db(tmp_path / "db")
    music = tmp_path / "music"
    write_wav(music / "A" / "x.wav")
    scan_directory(str(music), conn)
    calls = []
    original = scanner.scan_file
    monkeypatch.setattr(scanner, "scan_file", lambda *a, **k: calls.append(a[0]) or original(*a, **k))
    scan_directory(str(music), conn)
    assert calls == []
    new = music / "A" / "y.wav"
    write_wav(new)
    scan_directory(str(music), conn)
    assert calls == [str(new)]


def test_scan_removes_deleted_files_and_orphans(tmp_path):
    conn = make_db(tmp_path / "db")
    music = tmp_path / "music"
    write_wav(music / "A" / "x.wav")
    write_wav(music / "B" / "y.wav")
    scan_directory(str(music), conn)
    os.remove(music / "B" / "y.wav")
    scan_directory(str(music), conn)
    assert titles(conn) == ["x"]
    assert [r[0] for r in conn.execute("SELECT title FROM albums")] == ["A"]


def test_scan_keeps_library_when_folder_missing(tmp_path):
    conn = make_db(tmp_path / "db")
    music = tmp_path / "music"
    write_wav(music / "A" / "x.wav")
    scan_directory(str(music), conn)
    os.rename(music, tmp_path / "otro")
    scan_directory(str(music), conn)
    assert titles(conn) == ["x"]


def test_scan_should_stop(tmp_path):
    conn = make_db(tmp_path / "db")
    music = tmp_path / "music"
    write_wav(music / "A" / "x.wav")
    assert scan_directory(str(music), conn, should_stop=lambda: True) == 0
    assert titles(conn) == []
