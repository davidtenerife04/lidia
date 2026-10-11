import base64
import hashlib
import os
import re
from pathlib import Path

import mutagen
from mutagen.flac import Picture

from core.logger import logger

SUPPORTED_EXTENSIONS = {'.flac', '.mp3', '.m4a', '.ogg', '.opus', '.wav'}
COVERS_DIR = Path.home() / ".cache" / "lidia" / "covers"
FOLDER_COVER_NAMES = ("cover", "folder", "front", "album", "artwork")
FOLDER_COVER_EXTS = (".jpg", ".jpeg", ".png", ".webp")
UNKNOWN = "Desconocido"
SCAN_VERSION = 3  # sube para forzar el reprocesado de todos los archivos

_EMAIL_RE = re.compile(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}")
_PHONE_BLOB_RE = re.compile(r"\+?[\d\s\-()]{7,}")
_SPACES_RE = re.compile(r"\s+")
_SEP_RUNS_RE = re.compile(r"\s*([\-\u2014|\u00b7])\s*([\-\u2014|\u00b7]\s*)+")


def _replace_phone(match):
    # Solo se borra la secuencia si tiene 7+ dígitos
    blob = match.group(0)
    if sum(c.isdigit() for c in blob) >= 7:
        return " "
    return blob


def _clean(text, default):
    """Quita emails/teléfonos de un campo y normaliza espacios y separadores."""
    if not text:
        return default
    value = _EMAIL_RE.sub(" ", text)
    value = _PHONE_BLOB_RE.sub(_replace_phone, value)
    value = _SPACES_RE.sub(" ", value)
    value = _SEP_RUNS_RE.sub(" ", value)
    value = value.strip(" \u2014|\u00b7-").strip()
    return value or default


# ---------------------------------------------------------------- portadas

def _image_ext(data):
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return ".png"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return ".webp"
    return ".jpg"


def _find_cover_bytes(audio):
    """Busca la imagen incrustada: FLAC, ID3 (mp3/wav), MP4 (m4a) y Ogg/Opus."""
    pictures = getattr(audio, "pictures", None)
    if pictures:
        front = [p for p in pictures if p.type == 3]
        return (front or pictures)[0].data

    tags = getattr(audio, "tags", None)
    if not tags:
        return None

    try:
        if hasattr(tags, "getall"):  # ID3
            apics = tags.getall("APIC")
            if apics:
                front = [a for a in apics if a.type == 3]
                return (front or apics)[0].data

        covr = tags.get("covr")  # MP4
        if covr:
            return bytes(covr[0])

        block = tags.get("metadata_block_picture")  # Ogg Vorbis / Opus
        if block:
            return Picture(base64.b64decode(block[0])).data
    except Exception:
        pass
    return None


def extract_cover(file_path):
    """Guarda la carátula incrustada en la caché y devuelve su ruta (o None)."""
    try:
        audio = mutagen.File(file_path)
        if audio is None:
            return None
        data = _find_cover_bytes(audio)
        if not data:
            return None

        os.makedirs(COVERS_DIR, exist_ok=True)
        cover_path = COVERS_DIR / (hashlib.md5(data).hexdigest() + _image_ext(data))
        if not cover_path.exists():
            cover_path.write_bytes(data)
        return str(cover_path)
    except Exception as e:
        logger.warning("Error extrayendo carátula de %s", file_path, exc_info=True)
        return None


def find_folder_cover(directory):
    """Busca cover.jpg / folder.png... junto a los archivos de audio."""
    try:
        names = {n.lower(): n for n in os.listdir(directory)}
    except OSError:
        return None
    for base in FOLDER_COVER_NAMES:
        for ext in FOLDER_COVER_EXTS:
            if base + ext in names:
                return str(Path(directory) / names[base + ext])
    return None


# ---------------------------------------------------------------- escáner

def _first(tags, key, default):
    try:
        values = tags.get(key)
    except Exception:
        return default
    if values:
        value = str(values[0]).strip()
        if value:
            return _clean(value, default)
    return default


def _parse_int(text):
    try:
        return int(str(text).split("/")[0])
    except (ValueError, TypeError):
        return 0


def _artist_id(name, cursor, cache):
    if name not in cache:
        cursor.execute("INSERT OR IGNORE INTO artists (name) VALUES (?)", (name,))
        cursor.execute("SELECT id FROM artists WHERE name = ?", (name,))
        cache[name] = cursor.fetchone()[0]
    return cache[name]


def _audio_quality(audio, file_path, duration):
    """Devuelve (bitrate en kbps, formato) del archivo."""
    info = getattr(audio, 'info', None)
    fmt = os.path.splitext(file_path)[1].lstrip('.').upper()
    if getattr(info, 'codec', '') == 'alac':
        fmt = 'ALAC'
    bitrate = int(getattr(info, 'bitrate', 0) or 0)
    if bitrate <= 0 and duration > 0:
        try:
            bitrate = int(os.path.getsize(file_path) * 8 / duration)
        except OSError:
            bitrate = 0
    return round(bitrate / 1000), fmt


def scan_file(file_path, cursor, artist_cache, root=None, folder_cover=None):
    """Lee los metadatos de un único archivo y actualiza la BD (pista, artista, álbum)."""
    root = root or os.path.dirname(file_path)
    try:
        audio = mutagen.File(file_path, easy=True)
        if audio is None:
            return False
        tags = audio.tags if audio.tags is not None else {}

        title = _first(tags, 'title', Path(file_path).stem)
        artist_name = _first(tags, 'artist', UNKNOWN)
        album_artist = _first(tags, 'albumartist', artist_name)
        album_title = _first(tags, 'album', UNKNOWN)
        if album_title in (None, "", UNKNOWN):
            # Sin álbum: se agrupa por la carpeta contenedora
            album_title = _clean(os.path.basename(root), UNKNOWN)
        track_number = _parse_int(_first(tags, 'tracknumber', '0'))
        duration = int(audio.info.length) if getattr(audio, 'info', None) else 0
        bitrate, fmt = _audio_quality(audio, file_path, duration)

        artist_id = _artist_id(artist_name, cursor, artist_cache)
        album_artist_id = _artist_id(album_artist, cursor, artist_cache)

        # Álbum: se agrupa por (título, artista del álbum) -> los
        # recopilatorios ya no se rompen en un álbum por artista.
        cursor.execute(
            "INSERT OR IGNORE INTO albums (title, artist_id) VALUES (?, ?)",
            (album_title, album_artist_id))
        cursor.execute(
            "SELECT id, cover_path FROM albums WHERE title = ? AND artist_id = ?",
            (album_title, album_artist_id))
        album_id, cover_path = cursor.fetchone()

        # La portada solo se extrae si el álbum aún no tiene una válida
        if not cover_path or not os.path.exists(cover_path):
            new_cover = extract_cover(file_path)
            if not new_cover and folder_cover:
                new_cover = folder_cover
            if new_cover:
                cursor.execute("UPDATE albums SET cover_path = ? WHERE id = ?",
                               (new_cover, album_id))

        cursor.execute("""
            INSERT INTO tracks (path, title, track_number, duration, mtime, album_id, artist_id, bitrate, format)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(path) DO UPDATE SET
                title=excluded.title,
                track_number=excluded.track_number,
                duration=excluded.duration,
                mtime=excluded.mtime,
                album_id=excluded.album_id,
                artist_id=excluded.artist_id,
                bitrate=excluded.bitrate,
                format=excluded.format
        """, (file_path, title, track_number, duration, os.path.getmtime(file_path),
              album_id, artist_id, bitrate, fmt))
        return True
    except Exception as e:
        logger.warning("Error procesando %s", file_path, exc_info=True)
        return False


def _cleanup_orphans(cursor):
    """Borra álbumes y artistas que quedaron sin pistas (cambios de metadatos)."""
    cursor.execute("DELETE FROM albums WHERE id NOT IN (SELECT DISTINCT album_id FROM tracks WHERE album_id IS NOT NULL)")
    cursor.execute("""DELETE FROM artists WHERE id NOT IN (SELECT DISTINCT artist_id FROM tracks WHERE artist_id IS NOT NULL)
                      AND id NOT IN (SELECT DISTINCT artist_id FROM albums WHERE artist_id IS NOT NULL)""")


def scan_directory(directory_path, db_conn, progress=None, should_stop=None):
    """
    Recorre un directorio, lee metadatos, extrae portadas y guarda en SQLite.
    Es incremental (usa mtime) y elimina de la biblioteca lo que ya no existe.
    Devuelve el número de archivos de audio vistos.
    """
    directory_path = os.path.abspath(directory_path)  # rutas absolutas en la BD
    cursor = db_conn.cursor()
    artist_cache = {}
    seen = 0

    # Versión de esquema: si es anterior, se reprocesa todo ignorando mtime
    force_rescan = False
    row = cursor.execute("SELECT value FROM meta WHERE key = 'scan_version'").fetchone()
    try:
        force_rescan = not row or int(row[0]) < SCAN_VERSION
    except (TypeError, ValueError):
        force_rescan = True

    for root, _, files in os.walk(directory_path):
        if should_stop and should_stop():
            break
        folder_cover = find_folder_cover(root)

        for file in sorted(files):
            if should_stop and should_stop():
                break
            if os.path.splitext(file)[1].lower() not in SUPPORTED_EXTENSIONS:
                continue

            file_path = os.path.join(root, file)
            seen += 1
            if progress and seen % 25 == 0:
                progress(seen)
                db_conn.commit()

            try:
                mtime = os.path.getmtime(file_path)
                cursor.execute("SELECT mtime FROM tracks WHERE path = ?", (file_path,))
                result = cursor.fetchone()
                if result and result[0] == mtime and not force_rescan:
                    continue
            except OSError:
                continue
            scan_file(file_path, cursor, artist_cache, root=root, folder_cover=folder_cover)

    db_conn.commit()

    # Limpieza: pistas borradas del disco (solo si la carpeta está accesible,
    # para no vaciar la biblioteca si el disco está desmontado)
    if os.path.isdir(directory_path) and not (should_stop and should_stop()):
        prefix = os.path.join(directory_path, "")
        cursor.execute("SELECT id, path FROM tracks WHERE substr(path, 1, ?) = ?",
                       (len(prefix), prefix))
        missing = [(row[0],) for row in cursor.fetchall() if not os.path.exists(row[1])]
        if missing:
            cursor.executemany("DELETE FROM tracks WHERE id = ?", missing)

    _cleanup_orphans(cursor)
    cursor.execute("INSERT INTO meta (key, value) VALUES ('scan_version', ?) "
                   "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                   (SCAN_VERSION,))
    db_conn.commit()

    if progress:
        progress(seen)
    return seen


def remove_folder_tracks(conn, folder):
    """Borra de la base de datos las pistas bajo `folder` y limpia artistas/álbumes huérfanos."""
    prefix = os.path.join(os.path.abspath(folder), "")
    conn.execute("DELETE FROM tracks WHERE substr(path, 1, ?) = ?", (len(prefix), prefix))
    _cleanup_orphans(conn.cursor())
    conn.commit()
