import os
import re

_LRC_RE = re.compile(r"\[(\d{1,2}):(\d{1,2}(?:\.\d+)?)\]")


def parse_lrc(text):
    """Convierte el contenido de un .lrc en lista ordenada de {time, text}."""
    out = []
    for line in text.splitlines():
        stamps = list(_LRC_RE.finditer(line))
        if not stamps:
            continue
        body = line[stamps[-1].end():].strip()
        if not body:
            continue
        for m in stamps:
            t = int(m.group(1)) * 60 + float(m.group(2))
            out.append((t, body))
    out.sort(key=lambda e: e[0])
    return [{'time': t, 'text': body} for t, body in out]


def load_lyrics(track_path):
    lrc = os.path.splitext(track_path)[0] + ".lrc"
    if not os.path.exists(lrc):
        return []
    try:
        with open(lrc, encoding="utf-8", errors="replace") as f:
            return parse_lrc(f.read())
    except OSError as e:
        print(f"Error leyendo {lrc}: {e}")
        return []
