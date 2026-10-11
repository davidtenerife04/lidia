"""
Servicio MPRIS2 (org.mpris.MediaPlayer2) para integrar el reproductor con el
escritorio: teclas multimedia, widget de KDE/GNOME, playerctl, pantalla de bloqueo...

Usa `jeepney` (pip install jeepney). Si no está instalado o no hay bus de sesión,
la aplicación sigue funcionando sin MPRIS.
Las órdenes llegan al hilo principal mediante señales de Qt.
"""
import threading
from queue import Empty, Queue

from core.logger import logger

from PyQt6.QtCore import QObject, pyqtSignal

BUS_NAME = "org.mpris.MediaPlayer2.reproductor"
OBJ_PATH = "/org/mpris/MediaPlayer2"
IFACE_ROOT = "org.mpris.MediaPlayer2"
IFACE_PLAYER = "org.mpris.MediaPlayer2.Player"
IFACE_PROPS = "org.freedesktop.DBus.Properties"
NO_TRACK = "/org/mpris/MediaPlayer2/TrackList/NoTrack"
LOOP_NAMES = ["None", "Playlist", "Track"]

INTROSPECTION = """<node>
 <interface name="org.mpris.MediaPlayer2">
  <method name="Raise"/><method name="Quit"/>
  <property name="CanQuit" type="b" access="read"/>
  <property name="CanRaise" type="b" access="read"/>
  <property name="HasTrackList" type="b" access="read"/>
  <property name="Identity" type="s" access="read"/>
  <property name="SupportedUriSchemes" type="as" access="read"/>
  <property name="SupportedMimeTypes" type="as" access="read"/>
 </interface>
 <interface name="org.mpris.MediaPlayer2.Player">
  <method name="Next"/><method name="Previous"/><method name="Pause"/>
  <method name="PlayPause"/><method name="Stop"/><method name="Play"/>
  <method name="Seek"><arg type="x" direction="in"/></method>
  <method name="SetPosition"><arg type="o" direction="in"/><arg type="x" direction="in"/></method>
  <method name="OpenUri"><arg type="s" direction="in"/></method>
  <signal name="Seeked"><arg type="x"/></signal>
  <property name="PlaybackStatus" type="s" access="read"/>
  <property name="LoopStatus" type="s" access="readwrite"/>
  <property name="Rate" type="d" access="readwrite"/>
  <property name="Shuffle" type="b" access="readwrite"/>
  <property name="Metadata" type="a{sv}" access="read"/>
  <property name="Volume" type="d" access="readwrite"/>
  <property name="Position" type="x" access="read"/>
  <property name="MinimumRate" type="d" access="read"/>
  <property name="MaximumRate" type="d" access="read"/>
  <property name="CanGoNext" type="b" access="read"/>
  <property name="CanGoPrevious" type="b" access="read"/>
  <property name="CanPlay" type="b" access="read"/>
  <property name="CanPause" type="b" access="read"/>
  <property name="CanSeek" type="b" access="read"/>
  <property name="CanControl" type="b" access="read"/>
 </interface>
 <interface name="org.freedesktop.DBus.Properties">
  <method name="Get"><arg type="s" direction="in"/><arg type="s" direction="in"/><arg type="v" direction="out"/></method>
  <method name="GetAll"><arg type="s" direction="in"/><arg type="a{sv}" direction="out"/></method>
  <method name="Set"><arg type="s" direction="in"/><arg type="s" direction="in"/><arg type="v" direction="in"/></method>
  <signal name="PropertiesChanged"><arg type="s"/><arg type="a{sv}"/><arg type="as"/></signal>
 </interface>
</node>"""


class MprisService(QObject):
    playRequested = pyqtSignal()
    pauseRequested = pyqtSignal()
    playPauseRequested = pyqtSignal()
    stopRequested = pyqtSignal()
    nextRequested = pyqtSignal()
    previousRequested = pyqtSignal()
    seekRequested = pyqtSignal(float)        # segundos relativos
    positionRequested = pyqtSignal(float)    # segundos absolutos
    shuffleRequested = pyqtSignal(bool)
    loopRequested = pyqtSignal(int)          # 0 off · 1 toda la cola · 2 una
    volumeRequested = pyqtSignal(float)      # 0..100
    raiseRequested = pyqtSignal()
    quitRequested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._lock = threading.Lock()
        self._router = None
        self._stop = threading.Event()
        self._track = None
        self._track_n = 0
        self._playing = False
        self._shuffle = False
        self._loop = 0
        self._volume = 1.0
        self._position = 0.0

    # ------------------------------------------------------------ arranque

    def start(self):
        threading.Thread(target=self._run, daemon=True, name="mpris").start()

    def stop(self):
        self._stop.set()
        router, self._router = self._router, None
        if router is not None:
            try:
                router.close()
            except Exception:
                pass

    def _run(self):
        try:
            from jeepney.bus_messages import MatchRule, message_bus
            from jeepney.io.threading import DBusRouter, open_dbus_connection
        except ImportError:
            logger.info("MPRIS desactivado: instala jeepney (pip install jeepney)")
            return
        try:
            router = DBusRouter(open_dbus_connection(bus="SESSION"))
            reply = router.send_and_get_reply(message_bus.RequestName(BUS_NAME))
            if reply.body and reply.body[0] not in (1, 4):  # PRIMARY_OWNER / ALREADY_OWNER
                logger.warning("MPRIS: el nombre del bus ya está en uso")
                router.close()
                return
            requests = Queue()
            router.filter(MatchRule(type="method_call", path=OBJ_PATH), queue=requests)
            self._router = router
        except Exception as e:
            logger.warning("MPRIS desactivado", exc_info=True)
            return

        while not self._stop.is_set():
            try:
                msg = requests.get(timeout=0.5)
            except Empty:
                continue
            try:
                self._handle(msg)
            except Exception as e:
                logger.warning("MPRIS: error atendiendo mensaje", exc_info=True)

    # ------------------------------------------------------------ propiedades

    def _metadata(self):
        t = self._track
        if not t:
            return {"mpris:trackid": ("o", NO_TRACK)}
        meta = {
            "mpris:trackid": ("o", f"/org/mpris/MediaPlayer2/Track/{self._track_n}"),
            "mpris:length": ("x", int(t.get("duration", 0)) * 1_000_000),
            "xesam:title": ("s", t.get("title", "")),
            "xesam:artist": ("as", [t.get("artist", "")]),
            "xesam:album": ("s", t.get("album", "")),
            "xesam:url": ("s", "file://" + t.get("path", "")),
        }
        if t.get("cover"):
            meta["mpris:artUrl"] = ("s", "file://" + t["cover"])
        return meta

    def _status(self):
        if not self._track:
            return "Stopped"
        return "Playing" if self._playing else "Paused"

    def _root_props(self):
        return {
            "CanQuit": ("b", True),
            "CanRaise": ("b", True),
            "HasTrackList": ("b", False),
            "Identity": ("s", "Lidia"),
            "SupportedUriSchemes": ("as", ["file"]),
            "SupportedMimeTypes": ("as", ["audio/flac", "audio/mpeg", "audio/mp4",
                                          "audio/ogg", "audio/x-wav"]),
        }

    def _player_props(self):
        return {
            "PlaybackStatus": ("s", self._status()),
            "LoopStatus": ("s", LOOP_NAMES[self._loop]),
            "Rate": ("d", 1.0),
            "Shuffle": ("b", self._shuffle),
            "Metadata": ("a{sv}", self._metadata()),
            "Volume": ("d", self._volume),
            "Position": ("x", int(self._position * 1_000_000)),
            "MinimumRate": ("d", 1.0),
            "MaximumRate": ("d", 1.0),
            "CanGoNext": ("b", True),
            "CanGoPrevious": ("b", True),
            "CanPlay": ("b", True),
            "CanPause": ("b", True),
            "CanSeek": ("b", True),
            "CanControl": ("b", True),
        }

    def _props_for(self, iface):
        if iface == IFACE_ROOT:
            return self._root_props()
        if iface == IFACE_PLAYER:
            return self._player_props()
        return None

    # ------------------------------------------------------------ mensajes entrantes

    def _handle(self, msg):
        from jeepney import HeaderFields, new_error, new_method_return

        fields = msg.header.fields
        iface = fields.get(HeaderFields.interface)
        member = fields.get(HeaderFields.member)
        body = msg.body
        send = self._router.send

        def ok(signature=None, data=()):
            send(new_method_return(msg, signature, data))

        def fail(name, text):
            send(new_error(msg, name, "s", (text,)))

        if iface == "org.freedesktop.DBus.Introspectable" and member == "Introspect":
            return ok("s", (INTROSPECTION,))

        if iface == IFACE_PROPS:
            with self._lock:
                if member == "Get":
                    props = self._props_for(body[0])
                    if props is None or body[1] not in props:
                        return fail("org.freedesktop.DBus.Error.UnknownProperty", body[1])
                    return ok("v", (props[body[1]],))
                if member == "GetAll":
                    props = self._props_for(body[0])
                    return ok("a{sv}", (props or {},))
            if member == "Set":
                self._set_property(body[0], body[1], body[2][1])
                return ok()
            return fail("org.freedesktop.DBus.Error.UnknownMethod", str(member))

        if iface == IFACE_ROOT:
            if member == "Raise":
                self.raiseRequested.emit()
            elif member == "Quit":
                self.quitRequested.emit()
            else:
                return fail("org.freedesktop.DBus.Error.UnknownMethod", str(member))
            return ok()

        if iface == IFACE_PLAYER:
            simple = {
                "Play": self.playRequested, "Pause": self.pauseRequested,
                "PlayPause": self.playPauseRequested, "Stop": self.stopRequested,
                "Next": self.nextRequested, "Previous": self.previousRequested,
            }
            if member in simple:
                simple[member].emit()
            elif member == "Seek":
                self.seekRequested.emit(body[0] / 1_000_000)
            elif member == "SetPosition":
                self.positionRequested.emit(body[1] / 1_000_000)
            elif member == "OpenUri":
                pass  # no soportado
            else:
                return fail("org.freedesktop.DBus.Error.UnknownMethod", str(member))
            return ok()

        fail("org.freedesktop.DBus.Error.UnknownInterface", str(iface))

    def _set_property(self, iface, name, value):
        if iface != IFACE_PLAYER:
            return
        if name == "Shuffle":
            self.shuffleRequested.emit(bool(value))
        elif name == "LoopStatus" and value in LOOP_NAMES:
            self.loopRequested.emit(LOOP_NAMES.index(value))
        elif name == "Volume":
            self.volumeRequested.emit(max(0.0, min(1.0, float(value))) * 100)

    # ------------------------------------------------------------ estado (hilo principal)

    def _emit_changed(self, names):
        router = self._router
        if router is None:
            return
        try:
            from jeepney import DBusAddress, new_signal
            with self._lock:
                props = self._player_props()
                changed = {n: props[n] for n in names}
            emitter = DBusAddress(OBJ_PATH, interface=IFACE_PROPS)
            router.send(new_signal(emitter, "PropertiesChanged", "sa{sv}as",
                                   (IFACE_PLAYER, changed, [])))
        except Exception as e:
            logger.warning("MPRIS: no se pudo emitir PropertiesChanged", exc_info=True)

    def set_track(self, track):
        with self._lock:
            self._track = track
            self._track_n += 1
            self._position = 0.0
            self._playing = True
        self._emit_changed(["Metadata", "PlaybackStatus"])

    def set_playing(self, playing):
        with self._lock:
            if self._playing == playing:
                return
            self._playing = playing
        self._emit_changed(["PlaybackStatus"])

    def set_stopped(self):
        with self._lock:
            self._track = None
            self._playing = False
            self._position = 0.0
        self._emit_changed(["Metadata", "PlaybackStatus"])

    def set_shuffle(self, enabled):
        with self._lock:
            self._shuffle = enabled
        self._emit_changed(["Shuffle"])

    def set_loop(self, mode):
        with self._lock:
            self._loop = mode
        self._emit_changed(["LoopStatus"])

    def set_volume(self, volume_0_100):
        with self._lock:
            self._volume = max(0.0, min(1.0, volume_0_100 / 100))
        self._emit_changed(["Volume"])

    def set_position(self, seconds):
        # Position no emite señal (lo pide la especificación): los clientes la consultan
        self._position = seconds
