import re

from PyQt6.QtCore import QAbstractListModel, QModelIndex, Qt, pyqtProperty, pyqtSignal

UNKNOWN = "Desconocido"

_STRONG_SPLIT = re.compile(
    r"\s*(?:,|;|\bfeat\.?(?=\s)|\bft\.?(?=\s)|\bfeaturing\b|(?<=\s)con(?=\s)|(?<=\s)x(?=\s))\s*",
    re.IGNORECASE)
_WEAK_SPLIT = re.compile(r"\s*(?:&|/|\+)\s*")


def _clean_parts(parts):
    return [p.strip(" ()[]") for p in parts if p and p.strip(" ()[]")]


def split_artists(name, known=None):
    """Separa «A, B feat. C» en ['A', 'B', 'C'] (sin repetidos, conservando el orden).

    «&», «/» y «+» solo separan si cada parte es un artista conocido (`known`, nombres
    en minúsculas), para que «Simon & Garfunkel» siga siendo un único artista.
    """
    result, seen = [], set()
    for segment in _clean_parts(_STRONG_SPLIT.split(name or "")):
        sub = _clean_parts(_WEAK_SPLIT.split(segment))
        if len(sub) > 1 and known and all(p.casefold() in known for p in sub):
            pieces = sub
        else:
            pieces = [segment]
        for p in pieces:
            if p.casefold() not in seen:
                seen.add(p.casefold())
                result.append(p)
    return result


def _search_clause(query, columns):
    """Cada palabra debe aparecer en alguna de las columnas (AND entre palabras)."""
    where, params = [], []
    for token in query.split():
        escaped = token.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        where.append("(" + " OR ".join(f"{c} LIKE ? ESCAPE '\\'" for c in columns) + ")")
        params.extend([f"%{escaped}%"] * len(columns))
    return where, params


_SORT_SQL = {
    'title': "tracks.title COLLATE NOCASE",
    'artist': ("artists.name COLLATE NOCASE, albums.title COLLATE NOCASE,"
               " tracks.track_number, tracks.title COLLATE NOCASE"),
    'album': ("albums.title COLLATE NOCASE, artists.name COLLATE NOCASE,"
              " tracks.track_number, tracks.title COLLATE NOCASE"),
    'added': "tracks.id DESC",
}


def known_artists(conn):
    return {r[0].casefold() for r in conn.execute("SELECT name FROM artists")}


def fetch_tracks(conn, query="", album_id=None, artist_id=None,
                 favorites_only=False, playlist_id=None, sort="default", smart=None,
                 artist_name=None):
    where, params = _search_clause(
        query, ("tracks.title", "artists.name", "albums.title"))

    joins, join_params = "", []
    if playlist_id is not None:
        joins += " JOIN playlist_tracks pt ON pt.track_id = tracks.id AND pt.playlist_id = ?"
        join_params.append(playlist_id)
    if favorites_only:
        joins += " JOIN favorites fav ON fav.track_id = tracks.id"
    if album_id is not None:
        where.append("tracks.album_id = ?")
        params.append(album_id)
    if artist_id is not None:
        where.append("(tracks.artist_id = ? OR albums.artist_id = ?)")
        params.extend([artist_id, artist_id])

    if artist_name is not None:
        escaped = artist_name.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        where.append("artists.name LIKE ? ESCAPE '\\'")
        params.append(f"%{escaped}%")
    if smart == "top":
        where.append("tracks.play_count > 0")
    elif smart == "played":
        where.append("tracks.last_played IS NOT NULL")

    sql = """
        SELECT tracks.id, tracks.title, artists.name, albums.title,
               tracks.path, albums.cover_path, tracks.duration
        FROM tracks
        LEFT JOIN artists ON tracks.artist_id = artists.id
        LEFT JOIN albums ON tracks.album_id = albums.id
    """ + joins
    if where:
        sql += " WHERE " + " AND ".join(where)
    limit = ""
    if smart == "top":
        sql += " ORDER BY tracks.play_count DESC, tracks.last_played DESC"
        limit = " LIMIT 100"
    elif smart == "played":
        sql += " ORDER BY tracks.last_played DESC"
        limit = " LIMIT 100"
    elif smart == "added":
        sql += " ORDER BY tracks.id DESC"
        limit = " LIMIT 100"
    elif playlist_id is not None:
        sql += " ORDER BY pt.position"
    elif favorites_only:
        sql += " ORDER BY fav.added_at DESC, fav.rowid DESC"
    elif album_id is not None:
        sql += " ORDER BY tracks.track_number, tracks.title COLLATE NOCASE"
    elif sort in _SORT_SQL:
        sql += " ORDER BY " + _SORT_SQL[sort]
    else:
        sql += (" ORDER BY artists.name COLLATE NOCASE, albums.title COLLATE NOCASE,"
                " tracks.track_number, tracks.title COLLATE NOCASE")

    tracks = [_track_dict(r) for r in conn.execute(sql + limit, join_params + params).fetchall()]
    if artist_name is not None:
        wanted = artist_name.casefold()
        known = known_artists(conn)
        tracks = [t for t in tracks
                  if t['artist'].casefold() == wanted
                  or wanted in (p.casefold() for p in split_artists(t['artist'], known))]
    return tracks


def _track_dict(r):
    return {
        'id': r[0],
        'title': r[1],
        'artist': r[2] or UNKNOWN,
        'album': r[3] or UNKNOWN,
        'path': r[4],
        'cover': r[5] or "",
        'duration': r[6] or 0,
    }


def fetch_tracks_by_ids(conn, ids):
    """Devuelve las pistas existentes en la biblioteca respetando el orden de `ids`."""
    result = []
    for track_id in ids:
        row = conn.execute("""
            SELECT tracks.id, tracks.title, artists.name, albums.title,
                   tracks.path, albums.cover_path, tracks.duration
            FROM tracks
            LEFT JOIN artists ON tracks.artist_id = artists.id
            LEFT JOIN albums ON tracks.album_id = albums.id
            WHERE tracks.id = ?""", (track_id,)).fetchone()
        if row:
            result.append(_track_dict(row))
    return result


def fetch_tracks_by_paths(conn, paths):
    """Devuelve las pistas existentes en la biblioteca respetando el orden de `paths`."""
    result = []
    for path in paths:
        row = conn.execute("""
            SELECT tracks.id, tracks.title, artists.name, albums.title,
                   tracks.path, albums.cover_path, tracks.duration
            FROM tracks
            LEFT JOIN artists ON tracks.artist_id = artists.id
            LEFT JOIN albums ON tracks.album_id = albums.id
            WHERE tracks.path = ?""", (path,)).fetchone()
        if row:
            result.append(_track_dict(row))
    return result


class TrackModel(QAbstractListModel):
    TitleRole = Qt.ItemDataRole.UserRole + 1
    ArtistRole = Qt.ItemDataRole.UserRole + 2
    AlbumRole = Qt.ItemDataRole.UserRole + 3
    PathRole = Qt.ItemDataRole.UserRole + 4
    CoverRole = Qt.ItemDataRole.UserRole + 5
    DurationRole = Qt.ItemDataRole.UserRole + 6
    FavoriteRole = Qt.ItemDataRole.UserRole + 7

    _KEYS = {
        TitleRole: 'title', ArtistRole: 'artist', AlbumRole: 'album',
        PathRole: 'path', CoverRole: 'cover', DurationRole: 'duration',
    }

    countChanged = pyqtSignal()

    def __init__(self, db_conn, favorites):
        super().__init__()
        self.db_conn = db_conn
        self.favorites = favorites      # conjunto compartido de ids favoritos
        self.tracks = []
        self.query = ""
        self.view = ("all", None)       # all | album | artist | favorites | playlist
        self.sort = "default"           # default | title | artist | album | added

    def roleNames(self):
        names = {role: key.encode() for role, key in self._KEYS.items()}
        names[self.FavoriteRole] = b'favorite'
        return names

    def rowCount(self, parent=None):
        return len(self.tracks)

    def data(self, index, role):
        if not index.isValid() or not (0 <= index.row() < len(self.tracks)):
            return None
        if role == self.FavoriteRole:
            return self.tracks[index.row()]['id'] in self.favorites
        key = self._KEYS.get(role)
        return self.tracks[index.row()][key] if key else None

    @pyqtProperty(int, notify=countChanged)
    def count(self):
        return len(self.tracks)

    def set_view(self, kind, view_id=None):
        self.view = (kind, view_id)
        self.reload()

    def reload(self):
        kind, vid = self.view
        tracks = fetch_tracks(
            self.db_conn, self.query,
            album_id=vid if kind == "album" else None,
            artist_id=vid if kind == "artist" else None,
            favorites_only=(kind == "favorites"),
            playlist_id=vid if kind == "playlist" else None,
            artist_name=vid if kind == "artistname" else None,
            sort=self.sort if kind == "all" else "default",
            smart=kind if kind in ("top", "played", "added") else None)
        # Sin cambios: se evita el reset para no interrumpir el scroll ni la selección
        if [t['id'] for t in tracks] == [t['id'] for t in self.tracks]:
            self.tracks = tracks
            return
        self.beginResetModel()
        self.tracks = tracks
        self.endResetModel()
        self.countChanged.emit()

    def refresh_id(self, track_id):
        for row, t in enumerate(self.tracks):
            if t['id'] == track_id:
                i = self.index(row)
                self.dataChanged.emit(i, i, [self.FavoriteRole])

    def remove_row(self, row):
        if 0 <= row < len(self.tracks):
            self.beginRemoveRows(QModelIndex(), row, row)
            del self.tracks[row]
            self.endRemoveRows()
            self.countChanged.emit()

    def remove_id(self, track_id):
        for row, t in enumerate(self.tracks):
            if t['id'] == track_id:
                self.remove_row(row)
                return


class AlbumModel(QAbstractListModel):
    IdRole = Qt.ItemDataRole.UserRole + 1
    TitleRole = Qt.ItemDataRole.UserRole + 2
    ArtistRole = Qt.ItemDataRole.UserRole + 3
    CoverRole = Qt.ItemDataRole.UserRole + 4
    CountRole = Qt.ItemDataRole.UserRole + 5

    _KEYS = {
        IdRole: 'id', TitleRole: 'title', ArtistRole: 'artist',
        CoverRole: 'cover', CountRole: 'trackCount',
    }

    countChanged = pyqtSignal()

    def __init__(self, db_conn):
        super().__init__()
        self.db_conn = db_conn
        self.albums = []
        self.query = ""

    def roleNames(self):
        names = {role: key.encode() for role, key in self._KEYS.items()}
        names[self.IdRole] = b'albumId'  # 'id' está reservado en QML
        return names

    def rowCount(self, parent=None):
        return len(self.albums)

    def data(self, index, role):
        if not index.isValid() or not (0 <= index.row() < len(self.albums)):
            return None
        key = self._KEYS.get(role)
        return self.albums[index.row()][key] if key else None

    @pyqtProperty(int, notify=countChanged)
    def count(self):
        return len(self.albums)

    def reload(self):
        where, params = _search_clause(self.query, ("albums.title", "artists.name"))
        sql = """
            SELECT albums.id, albums.title, artists.name, albums.cover_path, COUNT(tracks.id)
            FROM albums
            LEFT JOIN artists ON albums.artist_id = artists.id
            LEFT JOIN tracks ON tracks.album_id = albums.id
        """
        if where:
            sql += " WHERE " + " AND ".join(where)
        sql += """
            GROUP BY albums.id
            HAVING COUNT(tracks.id) > 0
            ORDER BY artists.name COLLATE NOCASE, albums.title COLLATE NOCASE
        """
        rows = self.db_conn.execute(sql, params).fetchall()

        self.beginResetModel()
        self.albums = [{
            'id': r[0], 'title': r[1], 'artist': r[2] or UNKNOWN,
            'cover': r[3] or "", 'trackCount': r[4],
        } for r in rows]
        self.endResetModel()
        self.countChanged.emit()


class ArtistModel(QAbstractListModel):
    IdRole = Qt.ItemDataRole.UserRole + 1
    NameRole = Qt.ItemDataRole.UserRole + 2
    AlbumCountRole = Qt.ItemDataRole.UserRole + 3
    TrackCountRole = Qt.ItemDataRole.UserRole + 4

    countChanged = pyqtSignal()

    def __init__(self, db_conn):
        super().__init__()
        self.db_conn = db_conn
        self.artists = []
        self.query = ""

    def roleNames(self):
        return {self.IdRole: b'artistId', self.NameRole: b'name',
                self.AlbumCountRole: b'albumCount', self.TrackCountRole: b'trackCount'}

    def rowCount(self, parent=None):
        return len(self.artists)

    def data(self, index, role):
        if not index.isValid() or not (0 <= index.row() < len(self.artists)):
            return None
        a = self.artists[index.row()]
        return {self.IdRole: a['id'], self.NameRole: a['name'],
                self.AlbumCountRole: a['albumCount'],
                self.TrackCountRole: a['trackCount']}.get(role)

    @pyqtProperty(int, notify=countChanged)
    def count(self):
        return len(self.artists)

    def reload(self):
        where, params = _search_clause(self.query, ("artists.name",))
        sql = """
            SELECT artists.id, artists.name,
                   COUNT(DISTINCT tracks.id), COUNT(DISTINCT albums.id)
            FROM artists
            LEFT JOIN albums ON albums.artist_id = artists.id
            LEFT JOIN tracks ON tracks.artist_id = artists.id
        """
        if where:
            sql += " WHERE " + " AND ".join(where)
        sql += """
            GROUP BY artists.id
            HAVING COUNT(DISTINCT tracks.id) > 0 OR COUNT(DISTINCT albums.id) > 0
            ORDER BY artists.name COLLATE NOCASE
        """
        rows = self.db_conn.execute(sql, params).fetchall()

        self.beginResetModel()
        self.artists = [{
            'id': r[0], 'name': r[1], 'trackCount': r[2], 'albumCount': r[3],
        } for r in rows]
        self.endResetModel()
        self.countChanged.emit()


class QueueModel(QAbstractListModel):
    """Cola de reproducción editable. `items` es la lista de pistas (dicts)."""
    TitleRole = Qt.ItemDataRole.UserRole + 1
    ArtistRole = Qt.ItemDataRole.UserRole + 2
    CoverRole = Qt.ItemDataRole.UserRole + 3
    DurationRole = Qt.ItemDataRole.UserRole + 4
    CurrentRole = Qt.ItemDataRole.UserRole + 5

    _KEYS = {TitleRole: 'title', ArtistRole: 'artist',
             CoverRole: 'cover', DurationRole: 'duration'}

    countChanged = pyqtSignal()
    currentChanged = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.items = []
        self.current = -1

    def roleNames(self):
        names = {role: key.encode() for role, key in self._KEYS.items()}
        names[self.CurrentRole] = b'isCurrent'
        return names

    def rowCount(self, parent=None):
        return len(self.items)

    def data(self, index, role):
        if not index.isValid() or not (0 <= index.row() < len(self.items)):
            return None
        if role == self.CurrentRole:
            return index.row() == self.current
        key = self._KEYS.get(role)
        return self.items[index.row()][key] if key else None

    @pyqtProperty(int, notify=countChanged)
    def count(self):
        return len(self.items)

    @pyqtProperty(int, notify=currentChanged)
    def currentIndex(self):
        return self.current

    def _mark(self, row):
        if 0 <= row < len(self.items):
            i = self.index(row)
            self.dataChanged.emit(i, i, [self.CurrentRole])

    def set_current(self, row):
        if row == self.current:
            return
        old, self.current = self.current, row
        self._mark(old)
        self._mark(row)
        self.currentChanged.emit()

    def set_items(self, items):
        self.beginResetModel()
        self.items = list(items)
        self.current = -1
        self.endResetModel()
        self.countChanged.emit()
        self.currentChanged.emit()

    def insert(self, row, track):
        row = max(0, min(row, len(self.items)))
        self.beginInsertRows(QModelIndex(), row, row)
        self.items.insert(row, track)
        self.endInsertRows()
        if row <= self.current:
            self.current += 1
            self.currentChanged.emit()
        self.countChanged.emit()

    def remove(self, row):
        if not 0 <= row < len(self.items):
            return
        self.beginRemoveRows(QModelIndex(), row, row)
        del self.items[row]
        self.endRemoveRows()
        if row < self.current:
            self.current -= 1
            self.currentChanged.emit()
        self.countChanged.emit()

    def move(self, src, dst):
        n = len(self.items)
        if not (0 <= src < n and 0 <= dst < n) or src == dst:
            return
        if not self.beginMoveRows(QModelIndex(), src, src, QModelIndex(),
                                  dst + 1 if dst > src else dst):
            return
        self.items.insert(dst, self.items.pop(src))
        self.endMoveRows()
        cur = self.current
        if cur == src:
            cur = dst
        elif src < cur <= dst:
            cur -= 1
        elif dst <= cur < src:
            cur += 1
        if cur != self.current:
            self.current = cur
            self.currentChanged.emit()

    def clear_except_current(self):
        keep = self.items[self.current] if 0 <= self.current < len(self.items) else None
        self.beginResetModel()
        self.items = [keep] if keep else []
        self.current = 0 if keep else -1
        self.endResetModel()
        self.countChanged.emit()
        self.currentChanged.emit()


class PlaylistModel(QAbstractListModel):
    IdRole = Qt.ItemDataRole.UserRole + 1
    NameRole = Qt.ItemDataRole.UserRole + 2
    CountRole = Qt.ItemDataRole.UserRole + 3

    countChanged = pyqtSignal()

    def __init__(self, db_conn):
        super().__init__()
        self.db_conn = db_conn
        self.playlists = []

    def roleNames(self):
        return {self.IdRole: b'playlistId', self.NameRole: b'name',
                self.CountRole: b'trackCount'}

    def rowCount(self, parent=None):
        return len(self.playlists)

    def data(self, index, role):
        if not index.isValid() or not (0 <= index.row() < len(self.playlists)):
            return None
        p = self.playlists[index.row()]
        return {self.IdRole: p['id'], self.NameRole: p['name'],
                self.CountRole: p['count']}.get(role)

    @pyqtProperty(int, notify=countChanged)
    def count(self):
        return len(self.playlists)

    def reload(self):
        rows = self.db_conn.execute("""
            SELECT p.id, p.name, COUNT(pt.track_id)
            FROM playlists p
            LEFT JOIN playlist_tracks pt ON pt.playlist_id = p.id
            GROUP BY p.id
            ORDER BY p.name COLLATE NOCASE""").fetchall()
        self.beginResetModel()
        self.playlists = [{'id': r[0], 'name': r[1], 'count': r[2]} for r in rows]
        self.endResetModel()
        self.countChanged.emit()
