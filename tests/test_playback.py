import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.playback import REPEAT_ALL, REPEAT_OFF, choose_next


def test_empty_queue():
    assert choose_next(0, -1, 0, False, REPEAT_OFF) is None


def test_sequential_and_end():
    assert choose_next(3, 0, 0, False, REPEAT_OFF) == (1, False)
    assert choose_next(3, 2, 0, False, REPEAT_OFF) is None


def test_repeat_all_wraps():
    assert choose_next(3, 2, 0, False, REPEAT_ALL) == (0, False)


def test_pending_has_priority_over_shuffle():
    assert choose_next(3, 0, 1, True, REPEAT_OFF) == (1, True)


def test_shuffle_never_repeats_current():
    rng = random.Random(1)
    for _ in range(50):
        i, used = choose_next(4, 2, 0, True, REPEAT_OFF, rng)
        assert i != 2 and not used


def test_single_track_shuffle_falls_back_to_sequence():
    assert choose_next(1, 0, 0, True, REPEAT_OFF) is None
    assert choose_next(1, 0, 0, True, REPEAT_ALL) == (0, False)
