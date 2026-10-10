import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.lyrics import load_lyrics, parse_lrc
from core.session import SessionStore


class FakeSettings:
    def __init__(self, data=None):
        self.data = dict(data or {})
        self.writes = []

    def value(self, key, default, type=None):
        if key not in self.data:
            return default
        v = self.data[key]
        if type is int:
            return int(v)
        if type is float:
            return float(v)
        if type is bool:
            return bool(v)
        return v

    def setValue(self, key, v):
        self.data[key] = v
        self.writes.append((key, v))

    def sync(self):
        pass


def test_parse_lrc_order():
    out = parse_lrc("[00:30]B\n[00:10]A\n")
    assert out == [{'time': 10.0, 'text': 'A'}, {'time': 30.0, 'text': 'B'}]


def test_parse_lrc_empty_lines_ignored():
    assert parse_lrc("\n[00:05]A\n\n") == [{'time': 5.0, 'text': 'A'}]


def test_parse_lrc_multiple_stamps_in_line():
    out = parse_lrc("[00:01][00:02]misma línea\n")
    assert out == [{'time': 1.0, 'text': 'misma línea'}, {'time': 2.0, 'text': 'misma línea'}]


def test_load_lyrics_missing(tmp_path):
    track = tmp_path / "song.mp3"
    track.write_text("x")
    assert load_lyrics(str(track)) == []


def test_load_lyrics_found(tmp_path):
    track = tmp_path / "song.mp3"
    track.write_text("x")
    (tmp_path / "song.lrc").write_text("[00:05]Hola\n[00:10]Mundo\n", encoding="utf-8")
    assert load_lyrics(str(track)) == [
        {'time': 5.0, 'text': 'Hola'},
        {'time': 10.0, 'text': 'Mundo'},
    ]


def test_session_save_load_roundtrip():
    s = FakeSettings()
    SessionStore(s).save(["/1.mp3", "/2.mp3"], 1, 12.5, True, 2)
    assert SessionStore(s).load() == {
        'paths': ['/1.mp3', '/2.mp3'], 'index': 1, 'position': 12.5, 'shuffle': True, 'repeat': 2}


def test_session_queue_not_rewritten_if_unchanged():
    s = FakeSettings()
    store = SessionStore(s)
    store.save(["/1.mp3", "/2.mp3"], 0, 0.0, False, 0)
    store.save(["/1.mp3", "/2.mp3"], 1, 1.5, True, 1)
    assert sum(k == "session/queue" for k, _ in s.writes) == 1
    store.save(["/1.mp3", "/3.mp3"], 1, 1.5, True, 1)
    assert sum(k == "session/queue" for k, _ in s.writes) == 2


def test_session_load_none_invalid_json():
    s = FakeSettings({"session/queue": "{invalido"})
    assert SessionStore(s).load() is None
