import os

import mutagen

from core.scanner import find_folder_cover, scan_file


class TagError(Exception):
    pass


def write_tags(path, title, artist, album):
    try:
        audio = mutagen.File(path, easy=True)
        if audio is None:
            raise TagError("No se pudo abrir el archivo de audio")
        audio['title'] = title.strip()
        audio['artist'] = artist.strip()
        audio['album'] = album.strip()
        audio['albumartist'] = artist.strip()
        audio.save()
    except TagError:
        raise
    except Exception as e:
        raise TagError(f"Error al guardar las etiquetas: {e}") from e


def rescan_track(conn, path):
    try:
        folder = os.path.dirname(path)
        cursor = conn.cursor()
        scan_file(path, cursor, {}, root=folder, folder_cover=find_folder_cover(folder))
        conn.commit()
    except Exception as e:
        raise TagError(f"Error al reescanear la pista: {e}") from e


def edit_tags(conn, path, title, artist, album):
    write_tags(path, title, artist, album)
    rescan_track(conn, path)
