import sys
import threading
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.control import ControlError, PlayerController


class FakeBackend:
    def __init__(self):
        self.calls = []
        self.queue = [{"id": 7, "title": "T", "artist": "A", "album": "B", "path": "/x"}]
        self.index = 0
        self.shuffle = False
        self.repeat = 0
        self._time = 12.5
        self.audio = SimpleNamespace(player=SimpleNamespace(path="/x", pause=False))

    def _rec(name):
        def f(self, *a):
            self.calls.append((name, a))
        return f

    play = _rec("play"); pause = _rec("pause"); togglePause = _rec("togglePause")
    stop = _rec("stop"); nextTrack = _rec("next"); prevTrack = _rec("prev")
    seek = _rec("seek"); seekRelative = _rec("seekRelative"); setVolume = _rec("setVolume")
    toggleShuffle = _rec("toggleShuffle"); setRepeat = _rec("setRepeat")
    queueClear = _rec("queueClear")

    def play_track_ids(self, ids, start=0):
        self.calls.append(("play_ids", (ids, start)))
        return ids != [404]

    def enqueue_track_ids(self, ids, next_up=False):
        self.calls.append(("enqueue", (ids, next_up)))
        return True

    def getVolume(self):
        return 80.0


def test_snapshot_and_simple_command():
    b = FakeBackend()
    c = PlayerController(b)
    snap = c.execute("next")
    assert b.calls == [("next", ())]
    assert snap["track"] == {"id": 7, "title": "T", "artist": "A", "album": "B"}
    assert snap["playing"] is True and snap["position"] == 12.5 and snap["queue_length"] == 1


def test_arguments_validated():
    b = FakeBackend()
    c = PlayerController(b)
    c.execute("set_volume", {"volume": 150})
    c.execute("seek", {"position": 3})
    assert b.calls == [("setVolume", (100.0,)), ("seek", (3.0,))]
    for cmd, args in [("seek", {}), ("seek", {"position": "x"}), ("seek", {"position": True}),
                      ("set_repeat", {"mode": 5}), ("nope", {})]:
        with pytest.raises(ControlError):
            c.execute(cmd, args)
    assert len(b.calls) == 2


def test_threaded_controller_from_other_thread():
    from PyQt6.QtCore import QCoreApplication, QTimer
    from core.control_qt import ThreadedController

    app = QCoreApplication.instance() or QCoreApplication([])
    b = FakeBackend()
    tc = ThreadedController(PlayerController(b))
    out = {}

    def worker():
        try:
            out["ok"] = tc.execute("toggle_pause")
            tc.execute("bogus")
        except ControlError as e:
            out["err"] = str(e)
        finally:
            QTimer.singleShot(0, app.quit)

    threading.Thread(target=worker).start()
    app.exec()
    assert b.calls == [("togglePause", ())]
    assert out["ok"]["queue_length"] == 1 and "bogus" in out["err"]


def test_track_commands():
    b = FakeBackend()
    c = PlayerController(b)
    c.execute("play_tracks", {"ids": [1, 2], "start": 1})
    c.execute("enqueue", {"ids": [3]})
    c.execute("play_next", {"ids": [4]})
    assert b.calls == [("play_ids", ([1, 2], 1)), ("enqueue", ([3], False)), ("enqueue", ([4], True))]
    for cmd, args in [("play_tracks", {"ids": []}), ("play_tracks", {"ids": ["a"]}),
                      ("play_tracks", {"ids": [1], "start": "0"}), ("play_tracks", {"ids": [404]}),
                      ("enqueue", {})]:
        with pytest.raises(ControlError):
            c.execute(cmd, args)
