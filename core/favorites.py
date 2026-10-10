class FavoritesService:
    def __init__(self, conn):
        self.conn = conn
        self.ids = {r[0] for r in conn.execute("SELECT track_id FROM favorites")}

    def is_favorite(self, track_id):
        return track_id in self.ids

    def set(self, track_id, favorite):
        if favorite:
            self.conn.execute("INSERT OR IGNORE INTO favorites (track_id) VALUES (?)", (track_id,))
            self.ids.add(track_id)
        else:
            self.conn.execute("DELETE FROM favorites WHERE track_id = ?", (track_id,))
            self.ids.discard(track_id)
        self.conn.commit()

    def toggle(self, track_id):
        favorite = track_id not in self.ids
        self.set(track_id, favorite)
        return favorite
