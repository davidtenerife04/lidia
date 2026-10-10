import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core import database
from core.models import fetch_tracks, split_artists


def make_db(tmp_path):
    database.DB_DIR = tmp_path
    database.DB_PATH = tmp_path / "library.db"
    return database.init_db()


def test_split_artists():
    assert split_artists("A, B feat. C") == ["A", "B", "C"]
    assert split_artists("X Ambassadors") == ["X Ambassadors"]
    assert split_artists("Bad Bunny x Feid") == ["Bad Bunny", "Feid"]
    assert split_artists("Simon & Garfunkel", {"bad bunny"}) == ["Simon & Garfunkel"]
    assert split_artists("Bad Bunny & Feid", {"bad bunny", "feid"}) == ["Bad Bunny", "Feid"]


def test_init_db_adds_stats_columns(tmp_path):
    conn = make_db(tmp_path)
    cols = {r[1] for r in conn.execute("PRAGMA table_info(tracks)")}
    assert {"play_count", "last_played"} <= cols


def test_smart_lists_and_artist_filter(tmp_path):
    conn = make_db(tmp_path)
    conn.execute("INSERT INTO artists (name) VALUES ('Bad Bunny x Feid')")
    conn.execute("INSERT INTO tracks (path, title, mtime, artist_id, play_count, last_played) "
                 "VALUES ('/a.mp3', 'A', 1, 1, 2, '2026-01-01')")
    conn.execute("INSERT INTO tracks (path, title, mtime, artist_id) VALUES ('/b.mp3', 'B', 1, 1)")
    conn.commit()
    assert [t['title'] for t in fetch_tracks(conn, smart="top")] == ["A"]
    assert [t['title'] for t in fetch_tracks(conn, smart="played")] == ["A"]
    assert len(fetch_tracks(conn, smart="added")) == 2
    assert len(fetch_tracks(conn, artist_name="Feid")) == 2
    assert fetch_tracks(conn, artist_name="Nadie") == []


def test_migrations_set_version_and_uids(tmp_path, monkeypatch):
    monkeypatch.setattr(database, "DB_DIR", tmp_path)
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "library.db")
    conn = database.init_db()
    assert conn.execute("PRAGMA user_version").fetchone()[0] == len(database.MIGRATIONS)
    conn.execute("INSERT INTO tracks (path, title, mtime) VALUES ('/a.mp3', 'A', 1)")
    conn.execute("INSERT INTO playlists (name) VALUES ('P')")
    uid, ts = conn.execute("SELECT uid, updated_at FROM tracks").fetchone()
    assert uid and ts
    puid = conn.execute("SELECT uid FROM playlists").fetchone()[0]
    conn.execute("DELETE FROM playlists")
    assert conn.execute("SELECT uid FROM tombstones WHERE kind='playlist'").fetchone()[0] == puid
    conn.commit()
    conn.close()
    conn = database.init_db()
    assert conn.execute("SELECT uid FROM tracks").fetchone()[0] == uid


def test_migration_backfills_legacy_db(tmp_path, monkeypatch):
    import sqlite3
    monkeypatch.setattr(database, "DB_DIR", tmp_path)
    path = tmp_path / "library.db"
    monkeypatch.setattr(database, "DB_PATH", path)
    conn = database.init_db()
    conn.close()
    raw = sqlite3.connect(path)
    raw.execute("PRAGMA user_version = 1")
    raw.execute("INSERT INTO tracks (path, title, mtime, uid) VALUES ('/x.mp3', 'X', 1, NULL)")
    raw.commit()
    raw.close()
    conn = database.init_db()
    assert conn.execute("SELECT uid FROM tracks WHERE path='/x.mp3'").fetchone()[0]
