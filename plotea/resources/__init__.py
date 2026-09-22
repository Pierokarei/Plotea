"""Application icon, drawn in code so it stays crisp at every size.

A single drawing routine feeds both the running application and the icon files
the installers need, so the taskbar and the desktop shortcut never drift apart.
"""
from __future__ import annotations

import os
import re

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import (QColor, QIcon, QPainter, QPen, QPixmap, QPolygonF)

HERE = os.path.dirname(os.path.abspath(__file__))

#: Sizes every desktop environment asks for at some point.
ICON_SIZES = (16, 24, 32, 48, 64, 128, 256, 512)

BACKGROUND = "#10233F"
BARS = ("#E64B35", "#4DBBD5", "#00A087")
BASELINE = "#FFFFFF"


def draw_logo(painter: QPainter, size: int):
    """Three ascending bars on a dark tile: readable down to 16 px."""
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(Qt.PenStyle.NoPen)

    radius = size * 0.22
    painter.setBrush(QColor(BACKGROUND))
    painter.drawRoundedRect(QRectF(0, 0, size, size), radius, radius)

    margin = size * 0.20
    inner = size - 2 * margin
    gap = inner * 0.12
    width = (inner - 2 * gap) / 3
    heights = (0.42, 0.68, 1.0)
    baseline = size - margin

    for index, factor in enumerate(heights):
        height = inner * factor
        x = margin + index * (width + gap)
        painter.setBrush(QColor(BARS[index]))
        painter.drawRoundedRect(
            QRectF(x, baseline - height, width, height),
            width * 0.22, width * 0.22)

    painter.setBrush(QColor(BASELINE))
    painter.drawRect(QRectF(margin, baseline, inner, max(size * 0.045, 1.0)))


#: Bumped whenever the glyphs below change shape: the files are cached under
#: this number, so an old drawing is never served from a previous version.
GLYPH_VERSION = 2


def _dock_pixmap(name: str, color: str, size: int = 32) -> QPixmap:
    """A glyph the style sheet needs as a file, drawn to our own palette.

    Thick strokes filling most of the square: Qt's own dock buttons are a few
    faint pixels that vanish on a dark title bar, and its drop-down marker is
    not drawn at all from a style sheet.
    """
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    pen = QPen(QColor(color))
    pen.setWidthF(max(size * 0.13, 1.8))
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    painter.setPen(pen)
    m = size * 0.16

    if name == "close":
        painter.drawLine(QPointF(m, m), QPointF(size - m, size - m))
        painter.drawLine(QPointF(size - m, m), QPointF(m, size - m))
    elif name == "chevron":
        # the drop-down marker: Qt draws all four borders of the CSS
        # triangle trick, which is why it came out as a grey square
        painter.drawPolyline(QPolygonF([
            QPointF(m, size * 0.38),
            QPointF(size / 2, size - m - size * 0.06),
            QPointF(size - m, size * 0.38)]))
    else:
        # detach: one diagonal arrow pointing out. Three strokes is all that
        # survives at 15 px; anything busier turns to mush.
        painter.drawLine(QPointF(m, size - m), QPointF(size - m, m))
        painter.drawPolyline(QPolygonF([
            QPointF(size - m - size * 0.34, m),
            QPointF(size - m, m),
            QPointF(size - m, m + size * 0.34)]))
    painter.end()
    return pixmap


def write_dock_icons(folder: str, color: str, hover: dict | None = None
                     ) -> dict:
    """Write the style-sheet glyphs as files, because Qt needs a URL for them.

    `hover` maps a glyph to the colour it takes under the pointer, e.g.
    {"close": "#D9484A"} for the red cross every browser has taught people to
    expect. Returns {name: path}, with "<name>_hover" for those; an empty dict
    when the folder cannot be written, in which case Qt keeps its own icons.
    """
    wanted = [(name, color) for name in ("float", "close", "chevron")]
    for name, hover_color in (hover or {}).items():
        wanted.append((f"{name}_hover", hover_color))
    paths = {}
    try:
        os.makedirs(folder, exist_ok=True)
        for key, glyph_color in wanted:
            name = key.removesuffix("_hover")
            tag = glyph_color.lstrip("#")
            path = os.path.join(folder,
                                f"dock-{name}-v{GLYPH_VERSION}-{tag}.png")
            if not os.path.exists(path):
                _dock_pixmap(name, glyph_color, 32).save(path, "PNG")
            paths[key] = path.replace("\\", "/")
    except OSError:
        return {}
    _purge_old_glyphs(folder)
    return paths


#: dock-<glyph>-v<version>-<colour>.png, and the unversioned first spelling.
_GLYPH_FILE = re.compile(
    r"^dock-(?:float|close|chevron)-(?:v(\d+)-)?[0-9A-Fa-f]{3,8}\.png$")


def _purge_old_glyphs(folder: str):
    """Drop the glyph files a previous GLYPH_VERSION left behind.

    They are dead weight the moment the drawing changes, and nothing else
    would ever remove them. Only files matching the generated name are
    touched, and a file that cannot be removed - held open by another
    instance, say - is simply left alone.
    """
    try:
        names = os.listdir(folder)
    except OSError:
        return
    for name in names:
        match = _GLYPH_FILE.match(name)
        if match is None or match.group(1) == str(GLYPH_VERSION):
            continue
        try:
            os.remove(os.path.join(folder, name))
        except OSError:
            pass


def logo_pixmap(size: int) -> QPixmap:
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    draw_logo(painter, size)
    painter.end()
    return pixmap


def app_icon() -> QIcon:
    """The application icon, from bundled files when available."""
    packaged = os.path.join(HERE, "plotea.ico")
    if os.path.exists(packaged):
        icon = QIcon(packaged)
        if not icon.isNull():
            return icon
    icon = QIcon()
    for size in ICON_SIZES:
        icon.addPixmap(logo_pixmap(size))
    return icon


def icon_path(extension: str = ".ico") -> str | None:
    """Path to a bundled icon file, or None when it was never generated."""
    path = os.path.join(HERE, f"plotea{extension}")
    return path if os.path.exists(path) else None
