import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core import database
from core.metadata import TagError, write_tags
from core.scanner import remove_folder_tracks


def make_db(tmp_path):
    database.DB_DIR = tmp_path
    database.DB_PATH = tmp_path / "library.db"
    return database.init_db()


def test_write_tags_invalid_file(tmp_path):
    f = tmp_path / "x.mp3"
    f.write_bytes(b"no es audio")
    with pytest.raises(TagError):
        write_tags(str(f), "t", "a", "b")


def test_remove_folder_tracks_cleans_orphans(tmp_path):
    conn = make_db(tmp_path)
    conn.execute("INSERT INTO artists (name) VALUES ('A')")
    conn.execute("INSERT INTO albums (title, artist_id) VALUES ('Al', 1)")
    conn.execute("INSERT INTO tracks (path, title, mtime, album_id, artist_id) VALUES ('/m/one/a.mp3','a',1,1,1)")
    conn.execute("INSERT INTO tracks (path, title, mtime) VALUES ('/m/onetwo/b.mp3','b',1)")
    conn.commit()
    remove_folder_tracks(conn, "/m/one")
    paths = [r[0] for r in conn.execute("SELECT path FROM tracks")]
    assert paths == ['/m/onetwo/b.mp3']
    assert conn.execute("SELECT COUNT(*) FROM albums").fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM artists").fetchone()[0] == 0
