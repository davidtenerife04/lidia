import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.models import QueueModel


def track(n):
    return {"title": f"t{n}", "artist": "a", "cover": "", "duration": n}


def make(n=5, current=0):
    q = QueueModel()
    q.set_items([track(i) for i in range(n)])
    q.set_current(current)
    return q


def order(q):
    return [t["title"] for t in q.items]


def test_set_items_resets_current():
    q = make()
    q.set_items([track(1)])
    assert q.count == 1 and q.currentIndex == -1


def test_insert_before_current_shifts_current():
    q = make(current=2)
    q.insert(0, track(9))
    assert q.currentIndex == 3 and q.items[3]["title"] == "t2"


def test_insert_after_current_keeps_current():
    q = make(current=2)
    q.insert(4, track(9))
    assert q.currentIndex == 2


def test_insert_clamps_row():
    q = make(n=2)
    q.insert(99, track(9))
    assert q.items[-1]["title"] == "t9"


def test_remove_before_current_shifts_current():
    q = make(current=3)
    q.remove(1)
    assert q.currentIndex == 2 and q.items[2]["title"] == "t3"


def test_remove_out_of_range_is_ignored():
    q = make()
    q.remove(10)
    q.remove(-1)
    assert q.count == 5


def test_move_current_item():
    q = make(current=1)
    q.move(1, 3)
    assert q.currentIndex == 3 and order(q) == ["t0", "t2", "t3", "t1", "t4"]


def test_move_across_current_forward():
    q = make(current=2)
    q.move(0, 3)
    assert q.currentIndex == 1 and q.items[1]["title"] == "t2"


def test_move_across_current_backward():
    q = make(current=2)
    q.move(4, 0)
    assert q.currentIndex == 3 and q.items[3]["title"] == "t2"


def test_move_invalid_is_ignored():
    q = make(current=2)
    q.move(1, 1)
    q.move(-1, 2)
    q.move(1, 9)
    assert order(q) == [f"t{i}" for i in range(5)] and q.currentIndex == 2


def test_clear_except_current():
    q = make(current=2)
    q.clear_except_current()
    assert order(q) == ["t2"] and q.currentIndex == 0


def test_clear_without_current():
    q = make(current=0)
    q.set_current(-1)
    q.clear_except_current()
    assert q.count == 0 and q.currentIndex == -1


def test_data_roles():
    q = make(current=1)
    assert q.data(q.index(1), QueueModel.CurrentRole) is True
    assert q.data(q.index(0), QueueModel.CurrentRole) is False
    assert q.data(q.index(2), QueueModel.TitleRole) == "t2"
    assert q.data(q.index(9), QueueModel.TitleRole) is None
