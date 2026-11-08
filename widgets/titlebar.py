"""Barre de titre personnalisée (déplacement, réduire, agrandir, fermer)."""
from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QLinearGradient, QPainter, QPen
from PySide6.QtWidgets import QAbstractButton, QHBoxLayout, QLabel, QVBoxLayout, QWidget

import theme
from config import APP_TITLE
from widgets import icons
from widgets.controls import GlassButton, GlassLine


class LogoMark(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(40, 40)

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        pal = theme.current()
        r = QRectF(0.5, 0.5, self.width() - 1, self.height() - 1)
        grad = QLinearGradient(r.topLeft(), r.bottomRight())
        grad.setColorAt(0, QColor(pal.accent_a))
        grad.setColorAt(1, QColor(pal.accent_b))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(grad))
        p.drawRoundedRect(r, 13, 13)
        sheen = QLinearGradient(0, r.top(), 0, r.bottom())
        sheen.setColorAt(0, QColor(255, 255, 255, 90))
        sheen.setColorAt(0.6, QColor(255, 255, 255, 0))
        p.setBrush(QBrush(sheen))
        p.drawRoundedRect(r, 13, 13)
        pm = icons.pixmap("image", pal.ink, 22, self.devicePixelRatioF())
        if not pm.isNull():
            p.drawPixmap(9, 9, pm)


class WindowButton(QAbstractButton):
    def __init__(self, kind: str, parent=None):
        super().__init__(parent)
        self._kind = kind                  # "min", "max", "close"
        self.setFixedSize(36, 36)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        hover = self.underMouse()
        c = QPointF(self.width() / 2, self.height() / 2)
        if hover:
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(255, 95, 95, 215) if self._kind == "close"
                       else theme.ov(30))
            p.drawEllipse(c, 15, 15)
        p.setPen(QPen(theme.ov(235 if hover else 170), 1.6,
                      Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap,
                      Qt.PenJoinStyle.RoundJoin))
        p.setBrush(Qt.BrushStyle.NoBrush)
        x, y = c.x(), c.y()
        if self._kind == "min":
            p.drawLine(QPointF(x - 5, y + 3), QPointF(x + 5, y + 3))
        elif self._kind == "max":
            if self.window().isMaximized():
                p.drawRoundedRect(QRectF(x - 5, y - 2, 7, 7), 1.5, 1.5)
                p.drawLine(QPointF(x - 2, y - 5), QPointF(x + 4, y - 5))
                p.drawLine(QPointF(x + 4, y - 5), QPointF(x + 4, y + 1))
            else:
                p.drawRoundedRect(QRectF(x - 5, y - 5, 10, 10), 2, 2)
        else:
            p.drawLine(QPointF(x - 4.5, y - 4.5), QPointF(x + 4.5, y + 4.5))
            p.drawLine(QPointF(x + 4.5, y - 4.5), QPointF(x - 4.5, y + 4.5))


class TitleBar(QWidget):
    searchChanged = Signal(object)  # GlassLine.changed émet un objet : les types doivent correspondre
    settingsRequested = Signal()

    def __init__(self, native_frame: bool = False, parent=None):
        super().__init__(parent)
        self._native = native_frame
        self.setFixedHeight(72)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(24, 16, 16, 8)
        lay.setSpacing(14)

        lay.addWidget(LogoMark())
        text = QVBoxLayout()
        text.setSpacing(0)
        brand = QLabel(APP_TITLE)
        brand.setObjectName("brand")
        sub = QLabel("Tri rapide de photos")
        sub.setObjectName("brandSub")
        text.addWidget(brand)
        text.addWidget(sub)
        lay.addLayout(text)
        lay.addSpacing(6)

        self.version = QLabel("")
        self.version.setObjectName("pill")
        self.version.setVisible(False)
        lay.addWidget(self.version, 0, Qt.AlignmentFlag.AlignVCenter)
        lay.addStretch(1)

        self.search = GlassLine("Rechercher dans la bibliothèque…", width=300)
        self.search.setMinimumHeight(38)
        self.search.changed.connect(self.searchChanged)
        lay.addWidget(self.search)
        gear = GlassButton("Réglages", "ghost", "sliders")
        gear.setToolTip("Réglages (Ctrl+,)")
        gear.clicked.connect(self.settingsRequested)
        lay.addWidget(gear)

        self._max_btn = None
        if not native_frame:
            btn_min = WindowButton("min")
            self._max_btn = WindowButton("max")
            btn_close = WindowButton("close")
            btn_min.clicked.connect(lambda: self.window().showMinimized())
            self._max_btn.clicked.connect(self.toggle_maximized)
            btn_close.clicked.connect(lambda: self.window().close())
            for b in (btn_min, self._max_btn, btn_close):
                lay.addWidget(b)

    def set_version(self, text: str, tone: str = "") -> None:
        self.version.setText(text)
        self.version.setVisible(bool(text))
        theme.set_tone(self.version, tone)

    def toggle_maximized(self) -> None:
        win = self.window()
        if win.isMaximized():
            win.showNormal()
        else:
            win.showMaximized()

    def refresh_state(self) -> None:
        if self._max_btn is not None:
            self._max_btn.update()

    # -- déplacement de la fenêtre sans cadre ---------------------------
    def mousePressEvent(self, event) -> None:
        if self._native or event.button() != Qt.MouseButton.LeftButton:
            return
        handle = self.window().windowHandle()
        if handle is not None:
            handle.startSystemMove()
            event.accept()

    def mouseDoubleClickEvent(self, event) -> None:
        if not self._native and event.button() == Qt.MouseButton.LeftButton:
            self.toggle_maximized()
