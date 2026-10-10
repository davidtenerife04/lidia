import json


class SessionStore:
    def __init__(self, settings):
        self.settings = settings
        self._queue_hash = None

    def save(self, paths, index, position, shuffle, repeat):
        s = self.settings
        digest = hash(tuple(paths))
        if digest != self._queue_hash:  # la cola solo se reescribe si cambia
            s.setValue("session/queue", json.dumps(paths))
            self._queue_hash = digest
        s.setValue("session/index", index)
        s.setValue("session/position", float(position))
        s.setValue("session/shuffle", shuffle)
        s.setValue("session/repeat", repeat)
        s.sync()

    def load(self):
        s = self.settings
        try:
            paths = json.loads(s.value("session/queue", "[]", type=str))
        except ValueError:
            return None
        return {
            'paths': paths,
            'index': int(s.value("session/index", -1, type=int)),
            'position': float(s.value("session/position", 0.0, type=float)),
            'shuffle': bool(s.value("session/shuffle", False, type=bool)),
            'repeat': int(s.value("session/repeat", 0, type=int)),
        }

    def mark_queue(self, paths):
        self._queue_hash = hash(tuple(paths))
