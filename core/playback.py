import random

REPEAT_OFF, REPEAT_ALL, REPEAT_ONE = 0, 1, 2


def choose_next(n, index, next_pending, shuffle, repeat, rng=random):
    """Decide la siguiente pista sin modificar nada: (índice, usa_pendiente) o None."""
    if n == 0:
        return None
    if next_pending > 0 and index + 1 < n:
        return index + 1, True
    if shuffle and n > 1:
        return rng.choice([k for k in range(n) if k != index]), False
    i = index + 1
    if i >= n:
        if repeat != REPEAT_ALL:
            return None
        i = 0
    return i, False
