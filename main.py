import locale
import os
import socket
import ssl
import tempfile
import random
import shutil
import sys
from pathlib import Path

# Los controles personalizados del QML necesitan un estilo que los permita
os.environ.setdefault("QT_QUICK_CONTROLS_STYLE", "Basic")

from PyQt6.QtCore import (QObject, QSettings, QStandardPaths, QStorageInfo,
                          QThread, QTimer, QUrl, pyqtProperty, pyqtSignal, pyqtSlot)
from PyQt6.QtQml import QQmlApplicationEngine
from PyQt6.QtGui import QAction, QIcon
from PyQt6.QtWidgets import QApplication, QFileDialog, QMenu, QSystemTrayIcon

from core.artist_images import fetch_photo
from core.logger import logger
from core.control import PlayerController
from core.control_qt import ThreadedController
from core.discovery import Announcer
from core.covers import CoverProvider
from core import tls
from core.database import DB_DIR, init_db
from core.favorites import FavoritesService
from core.lyrics import load_lyrics
from core.models import (AlbumModel, ArtistModel, PlaylistModel, QueueModel, known_artists, split_artists,
                         TrackModel, fetch_tracks, fetch_tracks_by_ids, fetch_tracks_by_paths)
from core import audiolab, sync
from core.server import LidiaServer, Limits
from core.player import AudioPlayer
from core.metadata import TagError, edit_tags
from core.playback import REPEAT_ALL, REPEAT_OFF, REPEAT_ONE, choose_next
from core.playlists import PlaylistsService
from core.session import SessionStore
from core.scanner import remove_folder_tracks, scan_directory

try:
    from core.mpris import MprisService
except Exception:  # sin PyQt/jeepney o sin bus: la app funciona igual
    MprisService = None



def _local_ip():
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        try:
            sock.connect(("10.255.255.255", 1))
            return sock.getsockname()[0]
        except OSError:
            return "127.0.0.1"


class ScannerThread(QThread):
    progress = pyqtSignal(int)
    finished_scan = pyqtSignal()

    def __init__(self, folders, parent=None):
        super().__init__(parent)
        self.folders = folders

    def run(self):
        conn = init_db()  # conexión propia de este hilo
        total = 0
        try:
            for folder in self.folders:
                base = total
                total += scan_directory(
                    folder, conn,
                    progress=lambda n, base=base: self.progress.emit(base + n),
                    should_stop=self.isInterruptionRequested)
        except Exception as e:
            logger.exception("Error durante el escaneo")
        finally:
            conn.close()
            self.finished_scan.emit()


class LabThread(QThread):
    done = pyqtSignal(str, object)
    failed = pyqtSignal(str)

    def __init__(self, kind, fn, parent=None):
        super().__init__(parent)
        self.kind = kind
        self.fn = fn

    def run(self):
        try:
            self.done.emit(self.kind, self.fn())
        except audiolab.LabError as e:
            self.failed.emit(str(e))
        except Exception as e:
            self.failed.emit(f"Error inesperado: {e}")


class ArtistPhotoThread(QThread):
    photo = pyqtSignal(str, str)

    def __init__(self, names, parent=None):
        super().__init__(parent)
        self.names = names

    def run(self):
        for name in self.names:
            if self.isInterruptionRequested():
                return
            path = fetch_photo(name)
            if path:
                self.photo.emit(name, path)


class PlayerBackend(QObject):
    # --- señales hacia QML ---
    timeUpdated = pyqtSignal(float, arguments=['seconds'])
    durationUpdated = pyqtSignal(float, arguments=['seconds'])
    trackChanged = pyqtSignal(str, str, str, str, str, int,
                              arguments=['title', 'artist', 'album', 'cover', 'path', 'trackId'])
    favoriteChanged = pyqtSignal(int, bool, arguments=['trackId', 'favorite'])
    playingChanged = pyqtSignal(bool, arguments=['playing'])
    shuffleChanged = pyqtSignal(bool, arguments=['enabled'])
    repeatChanged = pyqtSignal(int, arguments=['mode'])
    scanningChanged = pyqtSignal(bool, arguments=['scanning'])
    scanProgress = pyqtSignal(int, arguments=['files'])
    message = pyqtSignal(str, arguments=['text'])
    sortChanged = pyqtSignal(str, arguments=['sort'])
    sleepRemainingChanged = pyqtSignal()
    labBusyChanged = pyqtSignal(bool, arguments=['busy'])
    labAnalyzed = pyqtSignal('QVariant', 'QVariantList', arguments=['info', 'peaks'])
    labPreviewReady = pyqtSignal(str, 'QVariantList', arguments=['path', 'peaks'])
    labFailed = pyqtSignal(str, arguments=['text'])
    labExported = pyqtSignal(str, arguments=['text'])

    # --- señales internas (vienen del hilo de mpv) ---
    _timeSig = pyqtSignal(float)
    _durationSig = pyqtSignal(float)
    _playingSig = pyqtSignal(bool)
    _endedSig = pyqtSignal()
    _autoAdvanceSig = pyqtSignal()
    _uploadedSig = pyqtSignal(str)
    _syncedSig = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.settings = QSettings("Lidia", "Lidia")
        self.db_conn = init_db()
        self.favorites_service = FavoritesService(self.db_conn)
        self.favorites = self.favorites_service.ids
        self.playlists_service = PlaylistsService(self.db_conn)
        self.track_model = TrackModel(self.db_conn, self.favorites)
        self.album_model = AlbumModel(self.db_conn)
        self.artist_model = ArtistModel(self.db_conn, self.settings.value("artistPhotos", True, type=bool))
        self.photo_thread = None
        self.lab_thread = None
        self.lab_player = None
        self.lab_dir = None
        self.playlist_model = PlaylistModel(self.db_conn)

        self.queue_model = QueueModel()
        self.history = []
        self._next_pending = 0  # pistas añadidas con «reproducir a continuación»
        self.shuffle = False
        self.repeat = REPEAT_OFF
        self._time = 0.0
        self.scanner_thread = None
        self.mpris = None
        self.session = SessionStore(self.settings)
        self._sleep_remaining = 0
        self.tray_available = False
        self._tray_pref = None

        # Reenviamos los eventos de mpv al hilo principal mediante señales
        self._timeSig.connect(self._on_time)
        self._durationSig.connect(self.durationUpdated)
        self._playingSig.connect(self._on_playing)
        self._endedSig.connect(self._on_track_ended)
        self._autoAdvanceSig.connect(self._on_auto_advanced)
        self._uploadedSig.connect(self._on_uploaded)
        self._syncedSig.connect(self._on_synced)
        self._planned = None  # (índice, usa_pendiente) de la pista precargada

        self.audio = AudioPlayer(
            on_time_update=self._timeSig.emit,
            on_track_end=self._endedSig.emit,
            on_duration_update=self._durationSig.emit,
            on_playing_change=self._playingSig.emit,
            on_auto_advance=self._autoAdvanceSig.emit,
        )
        self.audio.set_crossfade(self._crossfade_secs())
        self.audio.set_replaygain(self.settings.value("replayGain", True, type=bool))
        self.audio.set_volume(self.getVolume())
        self.audio.set_equalizer(self.getEqualizer())

        # Orden configurable de la lista "todos"
        sort = str(self.settings.value("track/sort", "default", type=str))
        self.track_model.sort = sort if sort in ("default", "title", "artist", "album", "added") else "default"

        # Temporizador de apagado: cuenta atrás de un segundo, al llegar a 0 pausa
        self._sleep_timer = QTimer(self)
        self._sleep_timer.setInterval(1000)
        self._sleep_timer.timeout.connect(self._sleep_tick)
        self._upload_scan_timer = QTimer(self)
        self._upload_scan_timer.setSingleShot(True)
        self._upload_scan_timer.setInterval(2000)
        self._upload_scan_timer.timeout.connect(self._upload_scan)

        self.control = ThreadedController(PlayerController(self))
        self.server = None
        self.announcer = None
        self.server_fingerprint = ""
        if self.settings.value("server/enabled", False, type=bool):
            self._start_server()

        if MprisService is not None:
            m = self.mpris = MprisService(self)
            m.playRequested.connect(self.play)
            m.pauseRequested.connect(self.pause)
            m.playPauseRequested.connect(self.togglePause)
            m.stopRequested.connect(self.stop)
            m.nextRequested.connect(self.nextTrack)
            m.previousRequested.connect(self.prevTrack)
            m.seekRequested.connect(self.seekRelative)
            m.positionRequested.connect(self.seek)
            m.shuffleRequested.connect(self._set_shuffle)
            m.loopRequested.connect(self.setRepeat)
            m.volumeRequested.connect(self.setVolume)
            m.set_volume(self.getVolume())
            m.start()

        # Guardado periódico de la sesión (cola y posición)
        self._session_timer = QTimer(self)
        self._session_timer.setInterval(10000)
        self._session_timer.timeout.connect(self.save_session)
        self._session_timer.start()

    # La cola vive en queue_model; `queue` e `index` son atajos
    @property
    def queue(self):
        return self.queue_model.items

    @queue.setter
    def queue(self, items):
        self.queue_model.set_items(items)

    @property
    def index(self):
        return self.queue_model.current

    @index.setter
    def index(self, value):
        self.queue_model.set_current(value)

    # ------------------------------------------------------------ biblioteca

    def reload_models(self):
        self.track_model.reload()
        self.album_model.reload()
        self.artist_model.reload()
        self.playlist_model.reload()
        self._fetch_artist_photos()

    def _fetch_artist_photos(self):
        if not self.artist_model.use_photos:
            return
        if self.photo_thread is not None and self.photo_thread.isRunning():
            return
        names = self.artist_model.missing_photos()
        if not names:
            return
        self.photo_thread = ArtistPhotoThread(names)
        self.photo_thread.photo.connect(self.artist_model.photo_ready)
        self.photo_thread.start()

    @pyqtSlot(str)
    def setQuery(self, query):
        query = query.strip()
        self.track_model.query = query
        self.album_model.query = query
        self.artist_model.query = query
        self.reload_models()

    # ------------------------------------------------------------ vistas de la lista de pistas

    @pyqtSlot()
    def showAll(self):
        self.track_model.set_view("all")

    @pyqtSlot(int)
    def openAlbum(self, album_id):
        self.track_model.set_view("album", album_id)

    @pyqtSlot(int)
    def openArtist(self, artist_id):
        self.track_model.set_view("artist", artist_id)

    @pyqtSlot(str)
    def openArtistByName(self, name):
        self.track_model.set_view("artistname", name)

    @pyqtSlot(str, result=list)
    def splitArtists(self, name):
        return split_artists(name, known_artists(self.db_conn))

    @pyqtSlot()
    def playArtist(self):
        self.playIndex(0)

    @pyqtSlot()
    def showFavorites(self):
        self.track_model.set_view("favorites")

    @pyqtSlot(str)
    def showSmart(self, kind):
        if kind in ("top", "played", "added"):
            self.track_model.set_view(kind)

    @pyqtSlot(int)
    def showPlaylist(self, playlist_id):
        self.track_model.set_view("playlist", playlist_id)

    # ------------------------------------------------------------ orden de la lista

    @pyqtProperty(str, notify=sortChanged)
    def sort(self):
        return str(self.track_model.sort)

    @pyqtSlot(str)
    def setSort(self, sort):
        if sort not in ("default", "title", "artist", "album", "added"):
            return
        self.track_model.sort = sort
        self.settings.setValue("track/sort", sort)
        if self.track_model.view[0] == "all":
            self.track_model.reload()
        self.sortChanged.emit(sort)

    @pyqtSlot(result=str)
    def getSort(self):
        return str(self.track_model.sort)

    # ------------------------------------------------------------ edición de etiquetas

    @pyqtSlot(int, str, str, str)
    def editTags(self, row, title, artist, album):
        if not 0 <= row < len(self.track_model.tracks):
            return
        track = self.track_model.tracks[row]
        try:
            edit_tags(self.db_conn, track['path'], title, artist, album)
        except TagError as e:
            self.message.emit(str(e))
            return
        self.reload_models()
        # Si la pista mantiene su fila, la vista se refresca con los nuevos datos
        for r, t in enumerate(self.track_model.tracks):
            if t['id'] == track['id']:
                i = self.track_model.index(r)
                self.track_model.dataChanged.emit(i, i, [])
                break

    @pyqtSlot(int, result='QVariant')
    def trackTags(self, row):
        if not 0 <= row < len(self.track_model.tracks):
            return {}
        t = self.track_model.tracks[row]
        return {'title': t['title'], 'artist': t['artist'], 'album': t['album']}

    # ------------------------------------------------------------ letras

    @pyqtSlot(str, result='QVariant')
    def lyrics(self, path):
        """Letra .lrc junto a la pista (mismo nombre base); [] si no existe."""
        return load_lyrics(path)

    # ------------------------------------------------------------ favoritos

    def _set_favorite(self, track_id, favorite):
        self.favorites_service.set(track_id, favorite)
        self.track_model.refresh_id(track_id)
        if not favorite and self.track_model.view[0] == "favorites":
            self.track_model.remove_id(track_id)
        self.favoriteChanged.emit(track_id, favorite)

    @pyqtSlot(int)
    def toggleFavorite(self, track_id):
        self._set_favorite(track_id, not self.favorites_service.is_favorite(track_id))

    @pyqtSlot(int)
    def toggleFavoriteAtRow(self, row):
        if 0 <= row < len(self.track_model.tracks):
            self.toggleFavorite(self.track_model.tracks[row]['id'])

    @pyqtSlot(int, result=bool)
    def isFavorite(self, track_id):
        return self.favorites_service.is_favorite(track_id)

    # ------------------------------------------------------------ listas de reproducción

    def _playlist_id(self, name, create=True):
        return self.playlists_service.get_id(name, create=create)

    def _add_tracks_to_playlist(self, playlist_id, track_ids):
        self.playlists_service.add_tracks(playlist_id, track_ids)
        self.playlist_model.reload()
        if self.track_model.view == ("playlist", playlist_id):
            self.track_model.reload()

    @pyqtSlot(int, int)
    def addRowToPlaylist(self, row, playlist_id):
        if 0 <= row < len(self.track_model.tracks):
            self._add_tracks_to_playlist(playlist_id, [self.track_model.tracks[row]['id']])

    @pyqtSlot(str, int, result=int)
    def createPlaylistWithRow(self, name, row):
        """Crea la lista (o usa la existente con ese nombre) y añade la pista `row`."""
        pid = self._playlist_id(name)
        if pid >= 0:
            self.playlist_model.reload()
            if row >= 0:
                self.addRowToPlaylist(row, pid)
        return pid

    @pyqtSlot(str, result=int)
    def saveQueueAsPlaylist(self, name):
        pid = self._playlist_id(name)
        if pid >= 0:
            self._add_tracks_to_playlist(pid, [t['id'] for t in self.queue])
        return pid

    @pyqtSlot(int, str)
    def renamePlaylist(self, playlist_id, name):
        if self.playlists_service.rename(playlist_id, name):
            self.playlist_model.reload()

    @pyqtSlot(int)
    def deletePlaylist(self, playlist_id):
        self.playlists_service.delete(playlist_id)
        self.playlist_model.reload()
        if self.track_model.view == ("playlist", playlist_id):
            self.track_model.set_view("all")

    @pyqtSlot(int)
    def removeRowFromPlaylist(self, row):
        kind, pid = self.track_model.view
        if kind != "playlist" or not 0 <= row < len(self.track_model.tracks):
            return
        tid = self.track_model.tracks[row]['id']
        self.playlists_service.remove_track(pid, tid)
        self.track_model.remove_row(row)
        self.playlist_model.reload()

    @pyqtSlot(int, result=str)
    def playlistName(self, playlist_id):
        return self.playlists_service.name(playlist_id)

    # ------------------------------------------------------------ reproducción

    def _play_at(self, i, record=True, load=True):
        if not 0 <= i < len(self.queue):
            return
        if record and self.index != -1:
            self.history.append(self.index)
            del self.history[:-200]
        self.index = i
        t = self.queue[i]
        self._time = 0.0
        self.trackChanged.emit(t['title'], t['artist'], t['album'], t['cover'], t['path'], t['id'])
        if self.mpris:
            self.mpris.set_track(t)
        if load:
            self.audio.play(t['path'])
        self._record_play(t['id'])
        self._replan()

    def _record_play(self, track_id):
        try:
            self.db_conn.execute(
                "UPDATE tracks SET play_count = play_count + 1, "
                "last_played = strftime('%Y-%m-%d %H:%M:%f', 'now') WHERE id = ?", (track_id,))
            self.db_conn.commit()
        except Exception as e:
            logger.warning("Error registrando la reproducción", exc_info=True)

    @pyqtSlot(int)
    def playIndex(self, i):
        """Reproduce la pista i de la lista visible; esa lista pasa a ser la cola."""
        self.queue = list(self.track_model.tracks)
        self.history = []
        self._next_pending = 0
        self.index = -1
        self._play_at(i)

    @pyqtSlot(int)
    def playAlbum(self, album_id):
        self.queue = fetch_tracks(self.db_conn, album_id=album_id)
        self.history = []
        self._next_pending = 0
        self.index = -1
        self._play_at(0)

    @pyqtSlot()
    def playShuffled(self):
        """Reproduce la lista visible en modo aleatorio."""
        self.queue = list(self.track_model.tracks)
        if not self.queue:
            return
        self.history = []
        self._next_pending = 0
        self.index = -1
        self._set_shuffle(True)
        self._play_at(random.randrange(len(self.queue)))

    def _choose_next(self):
        return choose_next(len(self.queue), self.index, self._next_pending, self.shuffle, self.repeat)

    def _take_next(self):
        choice = self._planned if self._planned is not None else self._choose_next()
        self._planned = None
        if choice is None:
            return None
        i, used_pending = choice
        if not 0 <= i < len(self.queue):
            return None
        if used_pending and self._next_pending > 0:
            self._next_pending -= 1
        return i

    def _gapless_enabled(self):
        return self.settings.value("gapless", True, type=bool)

    def _replan(self):
        """Precarga en mpv la pista siguiente (o limpia la precarga si no procede)."""
        self._planned = None
        crossfade = self._crossfade_secs() > 0
        self.audio.set_crossfade(self._crossfade_secs())
        choice = None
        if self.repeat != REPEAT_ONE and self.index != -1 and (crossfade or self._gapless_enabled()):
            choice = self._choose_next()
            if choice is not None and not 0 <= choice[0] < len(self.queue):
                choice = None
        path = self.queue[choice[0]]['path'] if choice else None
        self._planned = choice
        if crossfade:
            self.audio.clear_preload()
            self.audio.set_crossfade_next(path)
        else:
            self.audio.set_crossfade_next(None)
            self.audio.preload(path)

    def _crossfade_secs(self):
        return max(0, min(10, self.settings.value("crossfade", 0, type=int)))

    def _on_auto_advanced(self):
        i = self._take_next()
        if i is None:
            return
        self._play_at(i, load=False)

    def _advance(self, auto):
        i = self._take_next()
        if i is not None:
            self._play_at(i)

    @pyqtSlot()
    def nextTrack(self):
        self._advance(auto=False)

    @pyqtSlot()
    def prevTrack(self):
        if self._time > 3 or not self.queue:
            self.audio.seek(0)
            return
        if self.shuffle and self.history:
            self._play_at(self.history.pop(), record=False)
        elif not self.shuffle and self.index > 0:
            self._play_at(self.index - 1, record=False)
        else:
            self.audio.seek(0)

    def _on_track_ended(self):
        if self.repeat == REPEAT_ONE and self.index != -1:
            self._play_at(self.index, record=False)
        else:
            self._advance(auto=True)

    def _on_playing(self, playing):
        self.playingChanged.emit(playing)
        if self.mpris:
            self.mpris.set_playing(playing)

    def _on_time(self, seconds):
        self._time = seconds
        self.timeUpdated.emit(seconds)
        if self.mpris:
            self.mpris.set_position(seconds)

    # ------------------------------------------------------------ edición de la cola

    @pyqtSlot(int)
    def playNext(self, row):
        """Inserta la pista `row` de la lista visible justo después de la actual."""
        if not 0 <= row < len(self.track_model.tracks):
            return
        self.history = []
        self.queue_model.insert(self.index + 1, dict(self.track_model.tracks[row]))
        self._next_pending += 1
        self._replan()

    @pyqtSlot(int)
    def addToQueue(self, row):
        if not 0 <= row < len(self.track_model.tracks):
            return
        self.history = []
        self.queue_model.insert(len(self.queue), dict(self.track_model.tracks[row]))
        self._replan()

    @pyqtSlot(int)
    def queueJump(self, i):
        self._next_pending = 0
        self._play_at(i)

    @pyqtSlot(int)
    def queueRemove(self, i):
        if i == self.index:
            return  # la pista que suena no se puede quitar
        self.history = []
        self._next_pending = 0
        self.queue_model.remove(i)
        self._replan()

    @pyqtSlot(int, int)
    def queueMove(self, src, dst):
        self.history = []
        self._next_pending = 0
        self.queue_model.move(src, dst)
        self._replan()

    @pyqtSlot()
    def queueClear(self):
        self.history = []
        self._next_pending = 0
        self.queue_model.clear_except_current()
        self._replan()

    def _start_server(self):
        lan = self.settings.value("server/lan", False, type=bool)
        host = "0.0.0.0" if lan else "127.0.0.1"
        port = int(self.settings.value("server/port", 8765, type=int))
        try:
            cert, key = tls.ensure_certificate(DB_DIR / "tls")
            self.server_fingerprint = tls.fingerprint(cert)
            self.server = LidiaServer(self.control, init_db, host, port, tls.server_context(cert, key),
                                      upload_dir=self._upload_dir(), on_upload=self._uploadedSig.emit,
                                      limits=self._server_limits(), on_sync=self._syncedSig.emit)
            self.server.start()
        except (OSError, ssl.SSLError) as e:
            self.server = None
            logger.error("No se pudo iniciar el servidor en %s:%s: %s", host, port, e)
            return
        if lan:
            self.announcer = Announcer(f"Lidia en {socket.gethostname()}", _local_ip(), port)
            self.announcer.start()

    def _server_limits(self):
        s = self.settings
        return Limits(
            allow_downloads=s.value("server/allowDownloads", True, type=bool),
            allow_uploads=s.value("server/allowUploads", False, type=bool),
            requests_per_minute=s.value("server/requestsPerMinute", 600, type=int),
            max_upload_mb=s.value("server/maxUploadMb", 1024, type=int),
            upload_quota_gb=s.value("server/uploadQuotaGb", 20, type=int),
            download_gb_per_day=s.value("server/downloadGbPerDay", 0, type=int))

    @pyqtSlot(int)
    def setRequestsPerMinute(self, value):
        value = max(0, min(6000, int(value)))
        self.settings.setValue("server/requestsPerMinute", value)
        if self.server is not None:
            self.server.limits.requests_per_minute = value

    @staticmethod
    def _upload_dir():
        music = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.MusicLocation)
        return str(Path(music or Path.home()) / "Lidia")

    def _on_synced(self):
        """Un cliente ha modificado favoritos/listas/reproducciones: refresca la interfaz."""
        self.favorites_service.reload()
        self.reload_models()

    def _on_uploaded(self, path):
        folder = self._upload_dir()
        libs = self._libraries()
        if folder not in libs:
            libs.append(folder)
            self.settings.setValue("libraries", libs)
        self._upload_scan_timer.start()

    def _upload_scan(self):
        if self.scanner_thread is not None and self.scanner_thread.isRunning():
            self._upload_scan_timer.start()
            return
        self._start_scan([self._upload_dir()])

    def _stop_server(self):
        if self.announcer is not None:
            self.announcer.stop()
            self.announcer = None
        if self.server is not None:
            self.server.stop()
            self.server = None

    def _server_info(self):
        if self.server is None:
            return {'serverRunning': False, 'serverPin': "", 'serverAddress': "", 'serverFingerprint': ""}
        host, port = self.server.address
        if host == "0.0.0.0":
            host = _local_ip()
        return {'serverRunning': True, 'serverPin': self.server.pairing.pin,
                'serverAddress': f"{host}:{port}", 'serverFingerprint': self.server_fingerprint}

    def play_track_ids(self, ids, start=0):
        """Sustituye la cola por las pistas `ids` y reproduce la de posición `start`."""
        items = fetch_tracks_by_ids(self.db_conn, ids)
        if not items:
            return False
        self.queue = items
        self.history = []
        self._next_pending = 0
        self.index = -1
        self._play_at(max(0, min(int(start), len(items) - 1)))
        return True

    def enqueue_track_ids(self, ids, next_up=False):
        items = fetch_tracks_by_ids(self.db_conn, ids)
        if not items:
            return False
        self.history = []
        for offset, t in enumerate(items):
            if next_up:
                self.queue_model.insert(self.index + 1 + offset, t)
                self._next_pending += 1
            else:
                self.queue_model.insert(len(self.queue), t)
        self._replan()
        return True

    # ------------------------------------------------------------ transporte

    @pyqtSlot()
    def play(self):
        if self.audio.player.path is not None:
            self.audio.set_pause(False)
        elif self.queue:
            self._play_at(max(self.index, 0))

    @pyqtSlot()
    def pause(self):
        self.audio.set_pause(True)

    @pyqtSlot()
    def stop(self):
        self.audio.stop()
        self.playingChanged.emit(False)
        if self.mpris:
            self.mpris.set_stopped()

    @pyqtSlot(float)
    def seekRelative(self, seconds):
        self.audio.seek(self._time + seconds)

    @pyqtSlot()
    def togglePause(self):
        self.audio.toggle_pause()

    @pyqtSlot(float)
    def seek(self, seconds):
        self.audio.seek(seconds, absolute=True)

    # ------------------------------------------------------------ aleatorio / repetir / volumen

    @pyqtSlot(bool)
    def _set_shuffle(self, enabled):
        self.shuffle = enabled
        self._replan()
        self.shuffleChanged.emit(enabled)
        if self.mpris:
            self.mpris.set_shuffle(enabled)

    @pyqtSlot()
    def toggleShuffle(self):
        self._set_shuffle(not self.shuffle)

    @pyqtSlot()
    def cycleRepeat(self):
        self.setRepeat((self.repeat + 1) % 3)

    @pyqtSlot(int)
    def setRepeat(self, mode):
        self.repeat = mode
        self._replan()
        self.repeatChanged.emit(mode)
        if self.mpris:
            self.mpris.set_loop(mode)

    @pyqtSlot(result='QVariant')
    def getSettings(self):
        s = self.settings
        return {
            'replayGain': s.value("replayGain", True, type=bool),
            'gapless': s.value("gapless", True, type=bool),
            'darkMode': s.value("darkMode", True, type=bool),
            'crossfade': self._crossfade_secs(),
            'closeToTray': s.value("closeToTray", True, type=bool),
            'trayAvailable': self.tray_available,
            'libraries': self._libraries(),
            'serverEnabled': self.settings.value("server/enabled", False, type=bool),
            'serverLan': self.settings.value("server/lan", False, type=bool),
            'artistPhotos': s.value("artistPhotos", True, type=bool),
            'allowDownloads': s.value("server/allowDownloads", True, type=bool),
            'allowUploads': s.value("server/allowUploads", False, type=bool),
            'requestsPerMinute': s.value("server/requestsPerMinute", 600, type=int),
            **self._server_info(),
        }

    @pyqtSlot(str, bool)
    def setSetting(self, key, value):
        if key not in ("replayGain", "gapless", "closeToTray", "darkMode", "serverEnabled", "serverLan", "artistPhotos",
                       "allowDownloads", "allowUploads"):
            return
        if key in ("serverEnabled", "serverLan"):
            self.settings.setValue("server/enabled" if key == "serverEnabled" else "server/lan", value)
            self._stop_server()
            if self.settings.value("server/enabled", False, type=bool):
                self._start_server()
            return
        if key in ("allowDownloads", "allowUploads"):
            self.settings.setValue("server/" + key, value)
            if self.server is not None:
                setattr(self.server.limits, "allow_downloads" if key == "allowDownloads" else "allow_uploads", value)
            return
        self.settings.setValue(key, value)
        if key == "artistPhotos":
            self.artist_model.use_photos = value
            self.artist_model.reload()
            self._fetch_artist_photos()
        elif key == "replayGain":
            self.audio.set_replaygain(value)
        elif key == "gapless":
            self._replan()
        elif key == "closeToTray" and getattr(self, "_tray_pref", None) is not None:
            self._tray_pref.setChecked(value)

    @pyqtSlot(int)
    def setCrossfade(self, seconds):
        self.settings.setValue("crossfade", max(0, min(10, int(seconds))))
        self._replan()

    @pyqtSlot(str, result=list)
    def removeLibrary(self, folder):
        """Quita la carpeta de la biblioteca y borra sus pistas de la base de datos."""
        libs = self._libraries()
        if folder not in libs:
            return libs
        if self.scanner_thread is not None and self.scanner_thread.isRunning():
            self.message.emit("Espera a que termine el escaneo")
            return libs
        libs.remove(folder)
        self.settings.setValue("libraries", libs)
        remove_folder_tracks(self.db_conn, folder)
        self.reload_models()
        return libs

    @pyqtSlot(result=bool)
    def closeToTray(self):
        return self.tray_available and self.settings.value("closeToTray", True, type=bool)

    @pyqtSlot(result=float)
    def getVolume(self):
        return float(self.settings.value("volume", 80, type=float))

    @pyqtSlot(float)
    def setVolume(self, volume):
        self.audio.set_volume(volume)
        self.settings.setValue("volume", float(volume))
        if self.mpris:
            self.mpris.set_volume(volume)

    # ------------------------------------------------------------ ecualizador

    @pyqtSlot(list)
    def setEqualizer(self, gains):
        gains = [float(g) if g else 0.0 for g in (gains or [])]
        gains = (gains + [0.0] * 10)[:10]
        self.settings.setValue("equalizer", gains)
        self.audio.set_equalizer(gains)

    @pyqtSlot(result=list)
    def getEqualizer(self):
        gains = self.settings.value("equalizer", [0.0] * 10, type=list)
        gains = [float(g) if g else 0.0 for g in gains]
        return (gains + [0.0] * 10)[:10]

    # ------------------------------------------------------------ temporizador de apagado

    @pyqtProperty(int, notify=sleepRemainingChanged)
    def sleepRemaining(self):
        return self._sleep_remaining

    @pyqtSlot(int)
    def setSleepTimer(self, minutes):
        if self._sleep_timer.isActive():
            self._sleep_timer.stop()
        if minutes <= 0:
            self._sleep_remaining = 0
            self.sleepRemainingChanged.emit()
            return
        self._sleep_remaining = minutes * 60
        self.sleepRemainingChanged.emit()
        self._sleep_timer.start()

    def _sleep_tick(self):
        self._sleep_remaining -= 1
        if self._sleep_remaining <= 0:
            self._sleep_timer.stop()
            self._sleep_remaining = 0
            self.pause()
        self.sleepRemainingChanged.emit()

    # ------------------------------------------------------------ escaneo

    def _libraries(self):
        return [str(p) for p in self.settings.value("libraries", [], type=list)]

    @staticmethod
    def _browse_locations():
        """Atajos del diálogo: home, música, raíz y todos los discos montados."""
        paths = [str(Path.home()),
                 QStandardPaths.writableLocation(QStandardPaths.StandardLocation.MusicLocation),
                 "/"]
        ignored = ("/boot", "/proc", "/sys", "/dev", "/snap", "/var", "/tmp")
        skip_fs = {"tmpfs", "devtmpfs", "squashfs", "overlay", "efivarfs", "proc", "sysfs", "cgroup2"}
        for vol in QStorageInfo.mountedVolumes():
            root = vol.rootPath()
            fs = bytes(vol.fileSystemType()).decode(errors="ignore")
            if (vol.isValid() and vol.isReady() and fs not in skip_fs
                    and not root.startswith(ignored)):
                paths.append(root)
        for extra in ("/mnt", "/media", f"/run/media/{os.environ.get('USER', '')}"):
            if os.path.isdir(extra):
                paths.append(extra)
        seen, result = set(), []
        for p in paths:
            if p and p not in seen and os.path.isdir(p):
                seen.add(p)
                result.append(p)
        return result

    @pyqtSlot()
    def openFolderDialog(self):
        dialog = QFileDialog(None, "Selecciona tu carpeta de música")
        dialog.setFileMode(QFileDialog.FileMode.Directory)
        dialog.setOption(QFileDialog.Option.ShowDirsOnly, True)
        dialog.setSidebarUrls([QUrl.fromLocalFile(p) for p in self._browse_locations()])
        if not dialog.exec():
            return
        folder = dialog.selectedFiles()[0] if dialog.selectedFiles() else ""
        if folder:
            libs = self._libraries()
            if folder not in libs:
                libs.append(folder)
                self.settings.setValue("libraries", libs)
            self._start_scan([folder])

    @pyqtSlot(list)
    def addFolders(self, urls):
        """Añade carpetas (o el padre de archivos) arrastradas y las escanea."""
        folders = []
        for url in urls:
            path = str(url)
            if path.startswith("file://"):
                path = QUrl(path).toLocalFile()
            if not path:
                continue
            if os.path.isdir(path):
                folders.append(path)
            elif os.path.isfile(path):
                parent = os.path.dirname(path)
                if parent:
                    folders.append(parent)
        libs = self._libraries()
        added = False
        for folder in folders:
            if folder not in libs:
                libs.append(folder)
                added = True
        if added:
            self.settings.setValue("libraries", libs)
        if folders:
            self._start_scan(folders)

    @pyqtSlot()
    def rescan(self):
        libs = self._libraries()
        if libs:
            self._start_scan(libs)

    def _start_scan(self, folders):
        if self.scanner_thread is not None and self.scanner_thread.isRunning():
            return
        self.scanner_thread = ScannerThread(folders)
        self.scanner_thread.progress.connect(self.scanProgress)
        self.scanner_thread.finished_scan.connect(self._on_scan_finished)
        self.scanningChanged.emit(True)
        self.scanProgress.emit(0)
        self.scanner_thread.start()

    def _on_scan_finished(self):
        self.reload_models()
        self.scanningChanged.emit(False)

    # ------------------------------------------------------------ cierre

    # ------------------------------------------------------------ interfaz

    @pyqtSlot(result='QVariant')
    def loadUi(self):
        s = self.settings
        return {
            'width': int(s.value("ui/width", 0, type=int)),
            'height': int(s.value("ui/height", 0, type=int)),
            'queueOpen': bool(s.value("ui/queueOpen", False, type=bool)),
            'sidebarWidth': max(64, min(420, int(s.value("ui/sidebarWidth", 236, type=int)))),
        }

    @pyqtSlot(int)
    def saveSidebarWidth(self, width):
        self.settings.setValue("ui/sidebarWidth", max(64, min(420, int(width))))

    @pyqtSlot(int, int, bool)
    def saveUi(self, width, height, queue_open):
        s = self.settings
        s.setValue("ui/width", width)
        s.setValue("ui/height", height)
        s.setValue("ui/queueOpen", queue_open)

    # ------------------------------------------------------------ sesión

    def save_session(self):
        """Guarda cola, pista actual y posición para retomar al abrir."""
        self.session.save([t['path'] for t in self.queue], self.index, self._time,
                          self.shuffle, self.repeat)
        self._publish_resume()

    def _publish_resume(self):
        """Mientras suena algo, deja «seguir escuchando» disponible para otros dispositivos."""
        player = self.audio.player
        if not (0 <= self.index < len(self.queue)) or player.path is None or player.pause:
            return
        uid = self.queue[self.index].get('uid')
        if uid:
            try:
                sync.set_resume(self.db_conn, {"uid": uid, "position": float(self._time),
                                               "at": sync.now_iso(), "device": socket.gethostname()})
            except Exception as e:
                logger.warning("Error guardando la posición de escucha", exc_info=True)

    @pyqtSlot()
    def restore_session(self):
        """Recupera la cola anterior y deja la pista actual en pausa donde se quedó."""
        data = self.session.load()
        if data is None:
            return
        items = fetch_tracks_by_paths(self.db_conn, data['paths'])
        if not items:
            return

        saved_index = data['index']
        current_path = data['paths'][saved_index] if 0 <= saved_index < len(data['paths']) else None
        idx = next((i for i, t in enumerate(items) if t['path'] == current_path), -1)

        self.queue = items
        self.session.mark_queue([t['path'] for t in items])
        self._set_shuffle(data['shuffle'])
        self.setRepeat(data['repeat'])

        if idx >= 0 and os.path.exists(items[idx]['path']):
            t = items[idx]
            pos = data['position']
            self.index = idx
            self._time = pos
            self.trackChanged.emit(t['title'], t['artist'], t['album'], t['cover'], t['path'], t['id'])
            if self.mpris:
                self.mpris.set_track(t)
            self.audio.play(t['path'], start=pos, paused=True)
            self._replan()

    # ------------------------------------------------------------ laboratorio de audio

    def _lab_start(self, kind, fn):
        if self.lab_thread is not None and self.lab_thread.isRunning():
            self.labFailed.emit("Espera a que termine la operación en curso")
            return
        t = self.lab_thread = LabThread(kind, fn, self)
        t.done.connect(self._lab_done)
        t.failed.connect(self._lab_failed)
        t.finished.connect(lambda: self.labBusyChanged.emit(False))
        self.labBusyChanged.emit(True)
        t.start()

    def _lab_failed(self, text):
        self.labFailed.emit(text)

    def _lab_done(self, kind, result):
        if kind == "analyze":
            self.labAnalyzed.emit(*result)
        elif kind == "preview":
            self.labPreviewReady.emit(*result)
        else:
            self.labExported.emit(result)

    @pyqtSlot(result=str)
    def labPickFile(self):
        start = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.MusicLocation)
        path, _ = QFileDialog.getOpenFileName(
            None, "Selecciona un archivo de audio", start,
            "Audio (*.wav *.flac *.mp3 *.ogg *.opus *.m4a *.aac *.wma *.aiff *.ape);;Todos (*)")
        return path

    @pyqtSlot(str)
    def labAnalyze(self, path):
        self.labStop()
        self._lab_start("analyze", lambda: (audiolab.analyze(path), audiolab.waveform(path)))

    @pyqtSlot(str, float, int, bool)
    def labPreview(self, path, sample_rate, bits, original):
        if self.lab_dir is None:
            self.lab_dir = tempfile.mkdtemp(prefix="lidia_lab_")
        out = os.path.join(self.lab_dir, "original.wav" if original else "procesado.wav")
        self.labStop()
        self._lab_start("preview", lambda: (out, audiolab.make_preview(path, out, sample_rate, bits, original)))

    @pyqtSlot(str)
    def labPlay(self, path):
        if not path or not os.path.isfile(path):
            return
        import mpv
        self.audio.set_pause(True)
        if self.lab_player is None:
            self.lab_player = mpv.MPV(video=False, ytdl=False, audio_display="no")
        self.lab_player.play(path)
        self.lab_player.pause = False

    @pyqtSlot()
    def labStop(self):
        if self.lab_player is not None:
            try:
                self.lab_player.stop()
            except Exception:
                pass

    @pyqtSlot(str, float, int, str, int, result=bool)
    def labExport(self, path, sample_rate, bits, fmt, bitrate):
        stem = os.path.splitext(os.path.basename(path))[0]
        suggested = os.path.join(os.path.dirname(path), f"{stem}_{int(sample_rate)}Hz_{bits}bit.{fmt}")
        out, _ = QFileDialog.getSaveFileName(None, "Guardar archivo exportado", suggested,
                                             f"{fmt.upper()} (*.{fmt})")
        if not out:
            return False
        if not out.lower().endswith("." + fmt):
            out += "." + fmt

        def job():
            real_sr, size = audiolab.export_file(path, out, sample_rate, bits, fmt, bitrate)
            note = f" (ajustado a {real_sr} Hz por el formato)" if real_sr != int(round(sample_rate)) else ""
            return f"Exportado: {os.path.basename(out)} · {size / 1024:.0f} KB{note}"

        self._lab_start("export", job)
        return True

    def shutdown(self):
        self.labStop()
        if self.lab_thread is not None and self.lab_thread.isRunning():
            self.lab_thread.wait(10000)
        if self.lab_player is not None:
            self.lab_player.terminate()
        if self.lab_dir:
            shutil.rmtree(self.lab_dir, ignore_errors=True)
        self._stop_server()
        self.save_session()
        if self.scanner_thread is not None and self.scanner_thread.isRunning():
            self.scanner_thread.requestInterruption()
            self.scanner_thread.wait(5000)
        if self.photo_thread is not None and self.photo_thread.isRunning():
            self.photo_thread.requestInterruption()
            self.photo_thread.wait(12000)
        if self.mpris:
            self.mpris.stop()
        self.audio.terminate()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setOrganizationName("Lidia")  # mismas claves que QSettings del backend y del QML
    app.setApplicationName("Lidia")
    locale.setlocale(locale.LC_NUMERIC, 'C')  # mpv lo exige

    engine = QQmlApplicationEngine()
    engine.addImageProvider("covers", CoverProvider())
    backend = PlayerBackend()
    app.aboutToQuit.connect(backend.shutdown)

    engine.rootContext().setContextProperty("backend", backend)
    engine.rootContext().setContextProperty("trackModel", backend.track_model)
    engine.rootContext().setContextProperty("albumModel", backend.album_model)
    engine.rootContext().setContextProperty("artistModel", backend.artist_model)
    engine.rootContext().setContextProperty("queueModel", backend.queue_model)
    engine.rootContext().setContextProperty("playlistModel", backend.playlist_model)

    backend.reload_models()

    qml_file = Path(__file__).parent / "ui" / "main.qml"
    engine.load(QUrl.fromLocalFile(str(qml_file)))

    if not engine.rootObjects():
        sys.exit(-1)

    window = engine.rootObjects()[0]

    def show_window():
        window.show()
        window.raise_()
        window.requestActivate()

    if backend.mpris:
        backend.mpris.raiseRequested.connect(show_window)
        backend.mpris.quitRequested.connect(app.quit)

    dark = backend.settings.value("darkMode", True, type=bool)
    icon = QIcon(str(Path(__file__).parent / "ui" / ("logo-white-256.png" if dark else "logo-256.png")))
    app.setWindowIcon(icon)
    app.setDesktopFileName("lidia")
    app.setQuitOnLastWindowClosed(False)
    tray = None
    if QSystemTrayIcon.isSystemTrayAvailable():
        backend.tray_available = True
        tray = QSystemTrayIcon(icon, app)
        tray.setToolTip("Lidia")
        menu = QMenu()
        for label, slot in (("Mostrar", show_window), ("Reproducir / Pausa", backend.togglePause),
                            ("Anterior", backend.prevTrack), ("Siguiente", backend.nextTrack)):
            menu.addAction(label).triggered.connect(lambda _=False, f=slot: f())
        menu.addSeparator()
        tray_pref = QAction("Cerrar a la bandeja", menu, checkable=True)
        tray_pref.setChecked(backend.settings.value("closeToTray", True, type=bool))
        tray_pref.toggled.connect(lambda v: backend.settings.setValue("closeToTray", v))
        backend._tray_pref = tray_pref
        menu.addAction(tray_pref)
        menu.addAction("Salir").triggered.connect(app.quit)
        tray.setContextMenu(menu)
        tray.activated.connect(lambda reason: show_window() if reason in (
            QSystemTrayIcon.ActivationReason.Trigger,
            QSystemTrayIcon.ActivationReason.DoubleClick) else None)
        tray.show()
        backend._tray, backend._tray_menu = tray, menu

    QTimer.singleShot(0, backend.restore_session)

    # Reescaneo incremental de las carpetas guardadas (detecta altas y bajas)
    QTimer.singleShot(400, backend.rescan)

    sys.exit(app.exec())
