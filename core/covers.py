import os
from urllib.parse import unquote

from PyQt6.QtCore import QRectF, QSize, Qt
from PyQt6.QtGui import QColor, QImage, QPainter, QPainterPath
from PyQt6.QtQuick import QQuickImageProvider


class CoverProvider(QQuickImageProvider):
    """
    Sirve portadas como miniaturas cuadradas con esquinas redondeadas.

    URL desde QML:  image://covers/<tamaño>;<radio 0..0.5>;<ruta codificada>
    Se hace en Python (y no con shaders) para que funcione con cualquier
    renderizador de Qt Quick y para no decodificar carátulas enormes a tamaño real.
    """

    def __init__(self):
        super().__init__(QQuickImageProvider.ImageType.Image)

    def requestImage(self, image_id, requested_size):
        size, ratio, path = 160, 0.0, ""
        try:
            size_s, ratio_s, path = image_id.split(";", 2)
            size, ratio = max(16, min(1024, int(size_s))), float(ratio_s)
        except ValueError:
            pass
        if not os.path.exists(path):
            path = unquote(path)

        out = QImage(size, size, QImage.Format.Format_ARGB32_Premultiplied)
        out.fill(QColor(0, 0, 0, 0))

        src = QImage(path)
        if src.isNull():
            return out, out.size()

        # Recorte central cuadrado + escalado suave
        side = min(src.width(), src.height())
        src = src.copy((src.width() - side) // 2, (src.height() - side) // 2, side, side)
        src = src.scaled(size, size, Qt.AspectRatioMode.IgnoreAspectRatio,
                         Qt.TransformationMode.SmoothTransformation)

        painter = QPainter(out)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        clip = QPainterPath()
        radius = ratio * size
        clip.addRoundedRect(QRectF(0, 0, size, size), radius, radius)
        painter.setClipPath(clip)
        painter.drawImage(0, 0, src)
        painter.end()
        return out, out.size()
