"""Icônes vectorielles (SVG intégrés, aucune ressource externe)."""
from __future__ import annotations

from PySide6.QtCore import QByteArray, QRectF, Qt
from PySide6.QtGui import QColor, QIcon, QLinearGradient, QPainter, QPainterPath, QPixmap

import theme

try:                                    # QtSvg est fourni avec PySide6
    from PySide6.QtSvg import QSvgRenderer
except ImportError:                     # pragma: no cover
    QSvgRenderer = None

_SVG = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" '
        'stroke="{c}" stroke-width="1.8" stroke-linecap="round" '
        'stroke-linejoin="round">{body}</svg>')

_BODIES = {
    "home": '<path d="m3 9 9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/><polyline points="9 22 9 12 15 12 15 22"/>',
    "grid": '<rect width="7" height="7" x="3" y="3" rx="1"/><rect width="7" height="7" x="14" y="3" rx="1"/>'
            '<rect width="7" height="7" x="14" y="14" rx="1"/><rect width="7" height="7" x="3" y="14" rx="1"/>',
    "image": '<rect width="18" height="18" x="3" y="3" rx="2" ry="2"/><circle cx="9" cy="9" r="2"/>'
             '<path d="m21 15-3.086-3.086a2 2 0 0 0-2.828 0L6 21"/>',
    "tag": '<path d="M12.586 2.586A2 2 0 0 0 11.172 2H4a2 2 0 0 0-2 2v7.172a2 2 0 0 0 .586 1.414l8.704 8.704'
           'a2.426 2.426 0 0 0 3.42 0l6.58-6.58a2.426 2.426 0 0 0 0-3.42z"/><circle cx="7.5" cy="7.5" r=".5" fill="{c}"/>',
    "chart": '<line x1="18" x2="18" y1="20" y2="10"/><line x1="12" x2="12" y1="20" y2="4"/>'
             '<line x1="6" x2="6" y1="20" y2="14"/>',
    "undo": '<path d="M3 7v6h6"/><path d="M21 17a9 9 0 0 0-9-9 9 9 0 0 0-6 2.3L3 13"/>',
    "arrow-left": '<path d="m12 19-7-7 7-7"/><path d="M19 12H5"/>',
    "arrow-right": '<path d="M5 12h14"/><path d="m12 5 7 7-7 7"/>',
    "plus": '<path d="M5 12h14"/><path d="M12 5v14"/>',
    "edit": '<path d="M12 20h9"/><path d="M16.5 3.5a2.12 2.12 0 0 1 3 3L7 19l-4 1 1-4Z"/>',
    "phone": '<rect width="14" height="20" x="5" y="2" rx="2" ry="2"/>'
             '<path d="M12 18h.01"/>',
    "video": '<path d="m16 13 5.223 3.482a.5.5 0 0 0 .777-.416V7.87a.5.5 0 0 0'
             '-.752-.432L16 10.5"/><rect x="2" y="6" width="14" height="12" rx="2"/>',
    "audio": '<polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"/>'
             '<path d="M15.54 8.46a5 5 0 0 1 0 7.07"/>'
             '<path d="M19.07 4.93a10 10 0 0 1 0 14.14"/>',
    "display": '<rect width="20" height="14" x="2" y="3" rx="2"/>'
               '<path d="M8 21h8"/><path d="M12 17v4"/>',
    "control": '<path d="m3 3 7.07 16.97 2.51-7.39 7.39-2.51L3 3z"/>'
               '<path d="m13 13 6 6"/>',
    "record": '<circle cx="12" cy="12" r="10"/>'
              '<circle cx="12" cy="12" r="4" fill="{c}"/>',
    "sliders": '<path d="M21 4h-7"/><path d="M10 4H3"/><path d="M21 12h-9"/>'
               '<path d="M8 12H3"/><path d="M21 20h-5"/><path d="M12 20H3"/>'
               '<path d="M14 2v4"/><path d="M8 10v4"/><path d="M16 18v4"/>',
    "terminal": '<polyline points="4 17 10 11 4 5"/>'
                '<line x1="12" x2="20" y1="19" y2="19"/>',
    "refresh": '<path d="M3 12a9 9 0 0 1 9-9 9.75 9.75 0 0 1 6.74 2.74L21 8"/>'
               '<path d="M21 3v5h-5"/>'
               '<path d="M21 12a9 9 0 0 1-9 9 9.75 9.75 0 0 1-6.74-2.74L3 16"/>'
               '<path d="M8 16H3v5"/>',
    "copy": '<rect width="14" height="14" x="8" y="8" rx="2" ry="2"/>'
            '<path d="M4 16c-1.1 0-2-.9-2-2V4c0-1.1.9-2 2-2h10c1.1 0 2 .9 2 2"/>',
    "play": '<polygon points="6 3 20 12 6 21 6 3" fill="{c}"/>',
    "stop": '<rect x="5" y="5" width="14" height="14" rx="2.5" fill="{c}"/>',
    "wifi": '<path d="M12 20h.01"/><path d="M2 8.82a15 15 0 0 1 20 0"/>'
            '<path d="M5 12.86a10 10 0 0 1 14 0"/>'
            '<path d="M8.5 16.43a5 5 0 0 1 7 0"/>',
    "folder": '<path d="M20 20a2 2 0 0 0 2-2V8a2 2 0 0 0-2-2h-7.9a2 2 0 0 1-1.69'
              '-.9L9.6 3.9A2 2 0 0 0 7.93 3H4a2 2 0 0 0-2 2v13a2 2 0 0 0 2 2Z"/>',
    "help": '<circle cx="12" cy="12" r="10"/>'
            '<path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"/><path d="M12 17h.01"/>',
    "trash": '<path d="M3 6h18"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6"/>'
             '<path d="M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>',
    "check": '<path d="M20 6 9 17l-5-5"/>',
    "info": '<circle cx="12" cy="12" r="10"/><path d="M12 16v-4"/>'
            '<path d="M12 8h.01"/>',
}

_cache: dict = {}


def pixmap(name: str, color: str = "#ffffff", size: int = 18,
           dpr: float = 1.0) -> QPixmap:
    """Pixmap de l'icône (vide si QtSvg est absent)."""
    key = (name, color, size, round(dpr, 2))
    if key in _cache:
        return _cache[key]
    pm = QPixmap()
    if QSvgRenderer is not None and name in _BODIES:
        body = _BODIES[name].replace("{c}", color)
        svg = _SVG.replace("{c}", color).replace("{body}", body)
        renderer = QSvgRenderer(QByteArray(svg.encode("utf-8")))
        px = max(1, int(size * dpr))
        pm = QPixmap(px, px)
        pm.fill(Qt.GlobalColor.transparent)
        pm.setDevicePixelRatio(dpr)
        painter = QPainter(pm)
        renderer.render(painter, QRectF(0, 0, size, size))
        painter.end()
    _cache[key] = pm
    return pm


def app_icon() -> QIcon:
    """Icône de l'application : carré dégradé + photo."""
    size = 256
    pm = QPixmap(size, size)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    pal = theme.current()
    grad = QLinearGradient(0, 0, size, size)
    grad.setColorAt(0, QColor(pal.accent_a))
    grad.setColorAt(1, QColor(pal.accent_b))
    path = QPainterPath()
    path.addRoundedRect(QRectF(16, 16, size - 32, size - 32), 58, 58)
    p.fillPath(path, grad)
    glyph = pixmap("image", pal.ink, 128, 1.0)
    if not glyph.isNull():
        p.drawPixmap(64, 64, glyph)
    p.end()
    return QIcon(pm)
