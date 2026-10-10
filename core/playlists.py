import sqlite3


class PlaylistsService:
    def __init__(self, conn):
        self.conn = conn

    def get_id(self, name, create=True):
        name = name.strip()
        if not name:
            return -1
        row = self.conn.execute("SELECT id FROM playlists WHERE name = ?", (name,)).fetchone()
        if row:
            return row[0]
        if not create:
            return -1
        cur = self.conn.execute("INSERT INTO playlists (name) VALUES (?)", (name,))
        self.conn.commit()
        return cur.lastrowid

    def add_tracks(self, playlist_id, track_ids):
        pos = self.conn.execute(
            "SELECT COALESCE(MAX(position), 0) FROM playlist_tracks WHERE playlist_id = ?",
            (playlist_id,)).fetchone()[0]
        for tid in track_ids:
            cur = self.conn.execute(
                "INSERT OR IGNORE INTO playlist_tracks (playlist_id, track_id, position) VALUES (?, ?, ?)",
                (playlist_id, tid, pos + 1))
            pos += cur.rowcount
        self.conn.commit()

    def rename(self, playlist_id, name):
        name = name.strip()
        if not name:
            return False
        try:
            self.conn.execute("UPDATE playlists SET name = ? WHERE id = ?", (name, playlist_id))
            self.conn.commit()
        except sqlite3.IntegrityError:
            return False
        return True

    def delete(self, playlist_id):
        self.conn.execute("DELETE FROM playlists WHERE id = ?", (playlist_id,))
        self.conn.commit()

    def remove_track(self, playlist_id, track_id):
        self.conn.execute("DELETE FROM playlist_tracks WHERE playlist_id = ? AND track_id = ?",
                          (playlist_id, track_id))
        self.conn.commit()

    def name(self, playlist_id):
        row = self.conn.execute("SELECT name FROM playlists WHERE id = ?", (playlist_id,)).fetchone()
        return row[0] if row else ""
