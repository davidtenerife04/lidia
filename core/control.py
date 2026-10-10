"""Capa de control del reproductor, independiente de Qt y de la interfaz.

Es el único punto de entrada previsto para quien controle Lidia desde fuera
(API HTTP, WebSocket, otros dispositivos). `execute` y `snapshot` deben
llamarse desde el hilo principal; desde otros hilos usa `ThreadedController`.
"""


class ControlError(Exception):
    pass


def _number(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ControlError("se esperaba un número")
    return float(value)


def _volume(value):
    return max(0.0, min(100.0, _number(value)))


def _repeat(value):
    if value not in (0, 1, 2) or isinstance(value, bool):
        raise ControlError("repeat debe ser 0, 1 o 2")
    return value


def _ids(value):
    if (not isinstance(value, list) or not value or len(value) > 5000
            or not all(isinstance(i, int) and not isinstance(i, bool) for i in value)):
        raise ControlError("ids debe ser una lista de enteros (1 a 5000)")
    return value


class PlayerController:
    """Traduce órdenes por nombre a llamadas del backend, validando los argumentos."""

    def __init__(self, backend):
        self.backend = backend
        b = backend
        self._commands = {
            "play": (b.play, None),
            "pause": (b.pause, None),
            "toggle_pause": (b.togglePause, None),
            "stop": (b.stop, None),
            "next": (b.nextTrack, None),
            "previous": (b.prevTrack, None),
            "seek": (b.seek, ("position", _number)),
            "seek_relative": (b.seekRelative, ("seconds", _number)),
            "set_volume": (b.setVolume, ("volume", _volume)),
            "toggle_shuffle": (b.toggleShuffle, None),
            "set_repeat": (b.setRepeat, ("mode", _repeat)),
            "queue_clear": (b.queueClear, None),
        }
        self._custom = {
            "play_tracks": self._play_tracks,
            "enqueue": lambda args: self._enqueue(args, next_up=False),
            "play_next": lambda args: self._enqueue(args, next_up=True),
        }

    @property
    def commands(self):
        return sorted([*self._commands, *self._custom])

    def _play_tracks(self, args):
        start = args.get("start", 0)
        if isinstance(start, bool) or not isinstance(start, int):
            raise ControlError("start debe ser un entero")
        if not self.backend.play_track_ids(_ids(args.get("ids")), start):
            raise ControlError("ninguna de las pistas existe")

    def _enqueue(self, args, next_up):
        if not self.backend.enqueue_track_ids(_ids(args.get("ids")), next_up=next_up):
            raise ControlError("ninguna de las pistas existe")

    def execute(self, command, args=None):
        args = args or {}
        if command in self._custom:
            self._custom[command](args)
            return self.snapshot()
        entry = self._commands.get(command)
        if entry is None:
            raise ControlError(f"orden desconocida: {command}")
        method, spec = entry
        if spec is None:
            method()
        else:
            name, convert = spec
            if name not in args:
                raise ControlError(f"falta el argumento: {name}")
            method(convert(args[name]))
        return self.snapshot()

    def snapshot(self):
        b = self.backend
        index = b.index
        queue = b.queue
        track = None
        if 0 <= index < len(queue):
            t = queue[index]
            track = {k: t.get(k) for k in ("id", "title", "artist", "album")}
        player = b.audio.player
        return {
            "playing": player.path is not None and not player.pause,
            "track": track,
            "position": float(b._time),
            "volume": b.getVolume(),
            "shuffle": bool(b.shuffle),
            "repeat": int(b.repeat),
            "queue_length": len(queue),
            "queue_index": index,
        }
