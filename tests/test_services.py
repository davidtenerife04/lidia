import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core import database
from core.favorites import FavoritesService
from core.playlists import PlaylistsService


def make_db(tmp_path):
    database.DB_DIR = tmp_path
    database.DB_PATH = tmp_path / "library.db"
    return database.init_db()


def make_track(conn, path="/t.mp3"):
    cur = conn.execute("INSERT INTO tracks (path, title, mtime) VALUES (?, 'T', 1)", (path,))
    conn.commit()
    return cur.lastrowid


def test_favorites_toggle_set_is_favorite(tmp_path):
    conn = make_db(tmp_path)
    svc = FavoritesService(conn)
    tid = make_track(conn)
    assert not svc.is_favorite(tid)
    assert svc.toggle(tid) is True
    assert svc.is_favorite(tid)
    assert conn.execute("SELECT COUNT(*) FROM favorites").fetchone()[0] == 1
    assert svc.toggle(tid) is False
    assert not svc.is_favorite(tid)
    svc.set(tid, True)
    assert svc.is_favorite(tid)
    svc.set(tid, False)
    assert not svc.is_favorite(tid)


def test_favorites_ids_same_object(tmp_path):
    conn = make_db(tmp_path)
    svc = FavoritesService(conn)
    ids = svc.ids
    tid = make_track(conn)
    svc.set(tid, True)
    assert svc.ids is ids
    assert tid in ids
    svc.toggle(tid)
    assert tid not in ids


def test_playlist_get_id(tmp_path):
    conn = make_db(tmp_path)
    svc = PlaylistsService(conn)
    assert svc.get_id("   ") == -1
    pid = svc.get_id("Mi lista")
    assert pid >= 0
    assert svc.get_id("Mi lista") == pid
    assert svc.get_id("Otra", create=False) == -1


def test_playlist_add_tracks_no_duplicates(tmp_path):
    conn = make_db(tmp_path)
    svc = PlaylistsService(conn)
    pid = svc.get_id("P")
    t1 = make_track(conn, "/1.mp3")
    t2 = make_track(conn, "/2.mp3")
    t3 = make_track(conn, "/3.mp3")
    svc.add_tracks(pid, [t1, t2])
    svc.add_tracks(pid, [t2, t3])
    rows = conn.execute(
        "SELECT track_id, position FROM playlist_tracks WHERE playlist_id = ? ORDER BY position",
        (pid,)).fetchall()
    assert rows == [(t1, 1), (t2, 2), (t3, 3)]


def test_playlist_rename_duplicate(tmp_path):
    conn = make_db(tmp_path)
    svc = PlaylistsService(conn)
    a = svc.get_id("A")
    svc.get_id("B")
    assert svc.rename(a, "Nuevo")
    assert svc.name(a) == "Nuevo"
    assert not svc.rename(a, "B")  # ya existe otra lista con ese nombre
    assert not svc.rename(a, "   ")
    assert svc.rename(a, "B2")


def test_playlist_delete_cascade(tmp_path):
    conn = make_db(tmp_path)
    svc = PlaylistsService(conn)
    pid = svc.get_id("P")
    svc.add_tracks(pid, [make_track(conn)])
    assert conn.execute("SELECT COUNT(*) FROM playlist_tracks").fetchone()[0] == 1
    svc.delete(pid)
    assert conn.execute("SELECT COUNT(*) FROM playlists").fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM playlist_tracks").fetchone()[0] == 0


def test_playlist_remove_track(tmp_path):
    conn = make_db(tmp_path)
    svc = PlaylistsService(conn)
    pid = svc.get_id("P")
    t1 = make_track(conn, "/1.mp3")
    t2 = make_track(conn, "/2.mp3")
    svc.add_tracks(pid, [t1, t2])
    svc.remove_track(pid, t1)
    rows = conn.execute(
        "SELECT track_id FROM playlist_tracks WHERE playlist_id = ? ORDER BY position", (pid,)).fetchall()
    assert rows == [(t2,)]


def test_playlist_name(tmp_path):
    conn = make_db(tmp_path)
    svc = PlaylistsService(conn)
    pid = svc.get_id("Mi lista")
    assert svc.name(pid) == "Mi lista"
    assert svc.name(9999) == ""
