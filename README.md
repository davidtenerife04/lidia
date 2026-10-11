# Lidia

Reproductor de música local para Linux, con servidor HTTPS integrado para acceso remoto desde el móvil u otros dispositivos.

## Requisitos

- Python >= 3.10
- **libmpv** (reproductor de audio)
- **ffmpeg/ffprobe** (laboratorio de audio)
- En el sistema: `pip install -r requirements.txt`

### Dependencias Python

```
PyQt6 >= 6.4       # interfaz QML
mutagen            # etiquetas y metadatos
python-mpv         # reproducción con mpv
jeepney            # MPRIS (integración con el escritorio Linux)
zeroconf           # anuncio mDNS del servidor
cryptography       # certificados TLS
```

## Ejecución

```
pip install -r requirements.txt
python main.py
```

Para escanear una carpeta desde la línea de comandos:

```
python scan.py /ruta/a/tu/musica
```

## Funcionalidades

### Reproducción
- Reproductor basado en mpv con reproducción sin pausa (gapless) y crossfade
- Cola de reproducción, historial y modos de repetición
- Reproducción aleatoria
- ReplayGain
- Ecualizador de 10 bandas
- Temporizador de sueño
- Letras sincronizadas (archivos .lrc)
- Controles MPRIS2 (teclas multimedia, widget del escritorio, playerctl)

### Biblioteca
- Escaneo de carpetas con mutagen (FLAC, MP3, M4A, OGG, OPUS, WAV)
- Extracción automática de carátulas
- Fotos de artista descargadas automáticamente
- Búsqueda por título, artista y álbum
- Listas de reproducción y favoritos
- Edición de etiquetas integrada
- Estadísticas de reproducción («Más escuchadas»)

### Servidor integrado
- Servidor HTTPS con certificados autofirmados (TLS)
- Acceso a la biblioteca desde el navegador o desde clientes móviles
- Emparejamiento por PIN con tokens Bearer
- Límite de peticiones por minuto y por dispositivo
- Descarga de pistas (individual o biblioteca completa en ZIP)
- Subida de archivos al servidor
- Sincronización de favoritos, listas y posición de reproducción entre dispositivos
- Anuncio del servicio en la red local mediante mDNS
- Interfaz web accesible desde cualquier ruta no `/api/`

### Laboratorio de audio
- Análisis técnico de archivos (formato, codec, sample rate, bits, bitrate, canales)
- Reducción de frecuencia de muestreo y profundidad de bits con vista previa audible
- Exportación a WAV, FLAC, MP3 y OGG con los parámetros elegidos
- El archivo original nunca se modifica

### Interfaz
- Tema oscuro/claro
- Barra lateral con navegación: Canciones, Álbumes, Artistas, Favoritos, Más escuchadas
- Panel de cola y panel de letras
- Ajustes: reproducción sin pausa, crossfade, modo oscuro, cerrar a bandeja, fotos de artista, límites del servidor y bibliotecas

## Estructura del proyecto

```
main.py              Backend principal (PlayerBackend: puente QML <-> core)
scan.py              CLI para escanear carpetas
core/
  database.py        SQLite con migraciones
  scanner.py         Escaneo y extracción de carátulas
  models.py          Consultas y modelos Qt (TrackModel, AlbumModel, ...)
  player.py          Envoltorio de mpv
  playback.py        Lógica de siguiente pista y repetición
  control.py         API de control (sin dependencia de Qt)
  control_qt.py      Adaptador seguro entre hilos
  server.py          Servidor HTTPS
  tls.py             Certificados TLS
  discovery.py       Anuncio mDNS
  sync.py            Sincronización entre dispositivos
  mpris.py           Servicio MPRIS2 (D-Bus)
  favorites.py       Favoritos
  playlists.py       Listas de reproducción
  session.py         Sesión y posición de reproducción
  lyrics.py          Letras (.lrc)
  metadata.py        Edición de etiquetas
  covers.py          Portadas
  artist_images.py   Fotos de artista
  audiolab.py        Laboratorio de audio (análisis y compresión)
  logger.py          Configuración de logging
ui/
  main.qml           Ventana principal
  Theme.qml          Singleton de tema (colores)
  SideBar.qml        Barra lateral de navegación
  SongsView.qml      Vista de canciones
  AlbumsView.qml     Vista de álbumes
  ArtistsView.qml    Vista de artistas
  PlayerBar.qml      Barra de reproducción
  QueuePanel.qml     Panel de cola
  LyricsPanel.qml    Panel de letras
  SettingsPopup.qml  Ajustes
  EqualizerPopup.qml Ecualizador
  AudioLabPopup.qml  Laboratorio de audio
  EditTagsPopup.qml  Editor de etiquetas
  NamePopup.qml      Entrada de nombre
  *.qml              Componentes reutilizables (Icon, IconButton, PillButton, ...)
tests/               Pruebas con pytest
```

## Log

Los errores se registran en `~/.local/share/lidia/lidia.log` además de la consola.

## Empaquetado

```
pyinstaller lidia.spec
```

Genera `dist/Lidia/` con QML, página web del servidor y libmpv empaquetados.

## Licencia

Uso personal.
