import os
import sqlite3
from pathlib import Path

from core.logger import logger

DB_DIR = Path.home() / ".local" / "share" / "lidia"
DB_PATH = DB_DIR / "library.db"


def _add_column(cursor, table, column, ddl):
    columns = {r[1] for r in cursor.execute(f"PRAGMA table_info({table})")}
    if column not in columns:
        cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}")


def _migration_1(cursor):
    _add_column(cursor, "tracks", "play_count", "INTEGER NOT NULL DEFAULT 0")
    _add_column(cursor, "tracks", "last_played", "TEXT")


def _migration_2(cursor):
    """Identidad estable (uid), updated_at y tombstones para sincronizar entre dispositivos."""
    for table in ("tracks", "playlists"):
        _add_column(cursor, table, "uid", "TEXT")
        _add_column(cursor, table, "updated_at", "TEXT")
        cursor.execute(f"UPDATE {table} SET uid = lower(hex(randomblob(16))) WHERE uid IS NULL")
        cursor.execute(f"UPDATE {table} SET updated_at = strftime('%Y-%m-%dT%H:%M:%fZ','now') "
                       f"WHERE updated_at IS NULL")
        cursor.execute(f"CREATE UNIQUE INDEX IF NOT EXISTS idx_{table}_uid ON {table}(uid)")
        cursor.execute(f"""
        CREATE TRIGGER IF NOT EXISTS trg_{table}_uid AFTER INSERT ON {table}
        WHEN NEW.uid IS NULL
        BEGIN
            UPDATE {table} SET uid = lower(hex(randomblob(16))) WHERE id = NEW.id;
        END""")
        cursor.execute(f"""
        CREATE TRIGGER IF NOT EXISTS trg_{table}_ins_ts AFTER INSERT ON {table}
        WHEN NEW.updated_at IS NULL
        BEGIN
            UPDATE {table} SET updated_at = strftime('%Y-%m-%dT%H:%M:%fZ','now') WHERE id = NEW.id;
        END""")

    cursor.execute("""
    CREATE TRIGGER IF NOT EXISTS trg_playlists_upd_ts AFTER UPDATE OF name ON playlists
    BEGIN
        UPDATE playlists SET updated_at = strftime('%Y-%m-%dT%H:%M:%fZ','now') WHERE id = NEW.id;
    END""")

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS tombstones (
        kind TEXT NOT NULL,
        uid TEXT NOT NULL,
        deleted_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
        PRIMARY KEY (kind, uid)
    )""")
    cursor.execute("""
    CREATE TRIGGER IF NOT EXISTS trg_playlists_del AFTER DELETE ON playlists
    BEGIN
        INSERT OR REPLACE INTO tombstones (kind, uid) VALUES ('playlist', OLD.uid);
    END""")

    cursor.execute("CREATE INDEX IF NOT EXISTS idx_playlist_tracks_track ON playlist_tracks(track_id);")


def _migration_3(cursor):
    _add_column(cursor, "tracks", "bitrate", "INTEGER NOT NULL DEFAULT 0")
    _add_column(cursor, "tracks", "format", "TEXT NOT NULL DEFAULT ''")


_NOW = "strftime('%Y-%m-%dT%H:%M:%fZ','now')"


def _migration_4(cursor):
    """Seguimiento de cambios en favoritos y listas para la sincronización."""
    _add_column(cursor, "favorites", "updated_at", "TEXT")
    cursor.execute(f"UPDATE favorites SET updated_at = {_NOW} WHERE updated_at IS NULL")
    cursor.execute(f"""
    CREATE TRIGGER IF NOT EXISTS trg_favorites_ins AFTER INSERT ON favorites
    BEGIN
        UPDATE favorites SET updated_at = {_NOW} WHERE track_id = NEW.track_id;
        DELETE FROM tombstones WHERE kind = 'favorite'
            AND uid = (SELECT uid FROM tracks WHERE id = NEW.track_id);
    END""")
    cursor.execute("""
    CREATE TRIGGER IF NOT EXISTS trg_favorites_del AFTER DELETE ON favorites
    BEGIN
        INSERT OR REPLACE INTO tombstones (kind, uid)
            SELECT 'favorite', uid FROM tracks WHERE id = OLD.track_id;
    END""")
    cursor.execute("CREATE TABLE IF NOT EXISTS sync_events (id TEXT PRIMARY KEY, "
                   "at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)")
    for event, row in (("INSERT", "NEW"), ("DELETE", "OLD")):
        cursor.execute(f"""
        CREATE TRIGGER IF NOT EXISTS trg_playlist_tracks_{event.lower()}_ts AFTER {event} ON playlist_tracks
        BEGIN
            UPDATE playlists SET updated_at = {_NOW} WHERE id = {row}.playlist_id;
        END""")


MIGRATIONS = [_migration_1, _migration_2, _migration_3, _migration_4]


def _migrate(conn):
    """Aplica las migraciones pendientes según PRAGMA user_version."""
    cursor = conn.cursor()
    version = cursor.execute("PRAGMA user_version").fetchone()[0]
    for number, migration in enumerate(MIGRATIONS, start=1):
        if number > version:
            migration(cursor)
            cursor.execute(f"PRAGMA user_version = {number}")
            conn.commit()


def init_db():
    """Crea la base de datos y las tablas si no existen y devuelve una conexión nueva.

    Cada hilo debe usar su propia conexión (el escáner abre la suya).
    """
    os.makedirs(DB_DIR, exist_ok=True)

    conn = sqlite3.connect(DB_PATH, timeout=30)
    cursor = conn.cursor()

    cursor.execute("PRAGMA foreign_keys = ON;")
    # WAL: permite leer desde la interfaz mientras el escáner escribe
    cursor.execute("PRAGMA journal_mode = WAL;")
    cursor.execute("PRAGMA synchronous = NORMAL;")

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS artists (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE NOT NULL
    )
    ''')

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS albums (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        artist_id INTEGER,
        year INTEGER,
        cover_path TEXT,
        FOREIGN KEY (artist_id) REFERENCES artists(id) ON DELETE CASCADE,
        UNIQUE(title, artist_id)
    )
    ''')

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS tracks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        path TEXT UNIQUE NOT NULL,
        title TEXT NOT NULL,
        track_number INTEGER,
        duration INTEGER,
        mtime REAL NOT NULL,
        album_id INTEGER,
        artist_id INTEGER,
        FOREIGN KEY (album_id) REFERENCES albums(id) ON DELETE CASCADE,
        FOREIGN KEY (artist_id) REFERENCES artists(id) ON DELETE CASCADE
    )
    ''')

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS favorites (
        track_id INTEGER PRIMARY KEY,
        added_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (track_id) REFERENCES tracks(id) ON DELETE CASCADE
    )
    ''')

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS playlists (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL UNIQUE COLLATE NOCASE
    )
    ''')

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS playlist_tracks (
        playlist_id INTEGER NOT NULL,
        track_id INTEGER NOT NULL,
        position INTEGER NOT NULL,
        PRIMARY KEY (playlist_id, track_id),
        FOREIGN KEY (playlist_id) REFERENCES playlists(id) ON DELETE CASCADE,
        FOREIGN KEY (track_id) REFERENCES tracks(id) ON DELETE CASCADE
    )
    ''')

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS meta (
        key TEXT PRIMARY KEY,
        value TEXT
    )
    ''')

    cursor.execute('CREATE INDEX IF NOT EXISTS idx_track_title ON tracks(title);')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_track_album ON tracks(album_id);')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_track_artist ON tracks(artist_id);')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_album_title ON albums(title);')

    _migrate(conn)

    conn.commit()
    return conn


if __name__ == "__main__":
    init_db()
    logger.info("Base de datos inicializada en: %s", DB_PATH)
