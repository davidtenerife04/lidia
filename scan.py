import sys

from core.database import init_db
from core.logger import logger
from core.scanner import scan_directory

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python scan.py /ruta/a/tu/musica")
        sys.exit(1)

    music_dir = sys.argv[1]
    print(f"Iniciando escaneo en: {music_dir}...")
    logger.info("Iniciando escaneo en: %s", music_dir)

    db_conn = init_db()
    total = scan_directory(
        music_dir, db_conn,
        progress=lambda n: print(f"\r  {n} archivos revisados", end="", flush=True))
    db_conn.close()

    print(f"\n¡Escaneo completado! ({total} archivos). Ya puedes ejecutar main.py")
    logger.info("Escaneo completado: %d archivos", total)
