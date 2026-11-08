"""Surfaces en verre : fond aurore animé, cartes, lignes de réglage, pile fluide."""
from __future__ import annotations

import math
import random
import time

from PySide6.QtCore import (QAbstractAnimation, QEasingCurve, QPointF,
                            QPropertyAnimation, QRectF, Qt, QTimer)
from PySide6.QtGui import (QBrush, QColor, QImage, QLinearGradient, QPainter,
                           QPainterPath, QPen, QPixmap, QRadialGradient)
from PySide6.QtWidgets import (QFrame, QGraphicsOpacityEffect, QHBoxLayout,
                               QLabel, QStackedWidget, QVBoxLayout, QWidget)

import theme


def _noise_tile(size: int = 96) -> QPixmap:
    """Grain très léger : casse les aplats et donne un aspect verre dépoli."""
    rng = random.Random(7)
    img = QImage(size, size, QImage.Format.Format_ARGB32)
    for y in range(size):
        for x in range(size):
            v = rng.randint(0, 255)
            img.setPixel(x, y, (rng.randint(0, 8) << 24) | (v << 16) | (v << 8) | v)
    return QPixmap.fromImage(img)


class AuroraBackground(QWidget):
    """Fond de la fenêtre : dégradé profond + halos colorés qui dérivent."""

    INTERVAL_MS = 42            # ≈ 24 images/s

    def __init__(self, parent=None):
        super().__init__(parent)
        self._radius = 24.0
        self._animated = True
        self._t0 = time.monotonic() - 3.0
        self._t_last = 3.0
        self._cache = QPixmap()
        self._noise = _noise_tile()
        self._timer = QTimer(self)
        self._timer.setInterval(self.INTERVAL_MS)
        self._timer.timeout.connect(self._tick)
        self._timer.start()

    # -- réglages ------------------------------------------------------
    def set_radius(self, radius: float) -> None:
        self._radius = float(radius)
        self.update()

    def set_animated(self, on: bool) -> None:
        on = bool(on)
        if on and not self._animated:
            self._t0 = time.monotonic() - self._t_last
        self._animated = on
        self.update()

    # -- animation -----------------------------------------------------
    def _tick(self) -> None:
        # Pas de repeinture si la fenêtre est cachée, réduite ou inactive :
        # l'animation ne coûte rien pendant que scrcpy tourne.
        if not self._animated or not self.isVisible() or theme.current().flat:
            return
        win = self.window()
        if win.isMinimized() or not win.isActiveWindow():
            return
        self.update()

    def _now(self) -> float:
        if self._animated:
            self._t_last = time.monotonic() - self._t0
        return self._t_last

    def _render_blobs(self, t: float) -> None:
        w = max(1, self.width() // 2)
        h = max(1, self.height() // 2)
        if self._cache.width() != w or self._cache.height() != h:
            self._cache = QPixmap(w, h)
        pal = theme.current()
        cp = QPainter(self._cache)
        cp.setRenderHint(QPainter.RenderHint.Antialiasing)
        base = QLinearGradient(0, 0, 0, h)
        base.setColorAt(0, QColor(pal.bg_top))
        base.setColorAt(1, QColor(pal.bg_bottom))
        cp.fillRect(0, 0, w, h, QBrush(base))
        biggest = max(w, h)
        cp.setPen(Qt.PenStyle.NoPen)
        for hexc, cx, cy, rr, ax, ay, speed, phase, alpha in pal.blobs:
            x = (cx + ax * math.sin(t * speed + phase)) * w
            y = (cy + ay * math.cos(t * speed * 0.8 + phase)) * h
            rad = rr * biggest
            grad = QRadialGradient(QPointF(x, y), rad)
            grad.setColorAt(0.0, theme.qcolor(hexc, alpha))
            grad.setColorAt(0.45, theme.qcolor(hexc, alpha * 0.40))
            grad.setColorAt(1.0, theme.qcolor(hexc, 0.0))
            cp.setBrush(QBrush(grad))
            cp.drawEllipse(QPointF(x, y), rad, rad)
        cp.end()

    # -- peinture ------------------------------------------------------
    def paintEvent(self, _event) -> None:
        self._render_blobs(self._now())
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        r = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        rad = self._radius
        path = QPainterPath()
        path.addRoundedRect(r, rad, rad)
        if rad > 0:
            p.setClipPath(path)
        p.drawPixmap(self.rect(), self._cache)

        if not theme.current().flat:  # reflet + grain : uniquement pour les palettes « verre »
            sheen = QLinearGradient(0, 0, 0, 220)
            sheen.setColorAt(0, QColor(255, 255, 255, 20))
            sheen.setColorAt(1, QColor(255, 255, 255, 0))
            p.fillRect(QRectF(0, 0, self.width(), 220), QBrush(sheen))
            p.setOpacity(0.55)
            p.drawTiledPixmap(self.rect(), self._noise)
            p.setOpacity(1.0)

        if rad > 0:
            p.setClipping(False)
            border = QLinearGradient(r.topLeft(), r.bottomRight())
            border.setColorAt(0, theme.ov(70))
            border.setColorAt(0.5, theme.ov(22))
            border.setColorAt(1, theme.ov(12))
            p.setPen(QPen(QBrush(border), 1.0))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawPath(path)


class Divider(QWidget):
    """Filet fin entre deux lignes de réglage."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(1)

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.fillRect(self.rect(), theme.ov(18))


class GlassCard(QFrame):
    """Carte de verre : fond translucide, bord lumineux, reflet spéculaire."""

    def __init__(self, title: str | None = None, subtitle: str | None = None,
                 parent=None, radius: float = 20.0):
        super().__init__(parent)
        self._radius = radius
        self._rows = 0
        self._v = QVBoxLayout(self)
        self._v.setContentsMargins(24, 20, 24, 8)
        self._v.setSpacing(0)
        if title:
            head = QWidget()
            hl = QVBoxLayout(head)
            hl.setContentsMargins(0, 0, 0, 10)
            hl.setSpacing(3)
            t = QLabel(title)
            t.setObjectName("cardTitle")
            hl.addWidget(t)
            if subtitle:
                s = QLabel(subtitle)
                s.setObjectName("cardSub")
                s.setWordWrap(True)
                hl.addWidget(s)
            self._v.addWidget(head)

    def add_row(self, widget: QWidget) -> None:
        if self._rows:
            self._v.addWidget(Divider())
        self._v.addWidget(widget)
        self._rows += 1

    def add_widget(self, widget: QWidget, stretch: int = 0) -> None:
        self._v.addWidget(widget, stretch)

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        rad = self._radius
        path = QPainterPath()
        path.addRoundedRect(r, rad, rad)

        pal = theme.current()
        if pal.flat:  # HyperOS : surface pleine, bord discret
            p.fillPath(path, QColor(pal.surface))
            p.setPen(QPen(theme.ov(26), 1.0))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawPath(path)
            return

        fill = QLinearGradient(0, r.top(), 0, r.bottom())
        fill.setColorAt(0, theme.ov(30))
        fill.setColorAt(1, theme.ov(12))
        p.fillPath(path, QBrush(fill))

        border = QLinearGradient(r.topLeft(), r.bottomRight())
        border.setColorAt(0, theme.ov(96))
        border.setColorAt(0.5, theme.ov(30))
        border.setColorAt(1, theme.ov(16))
        p.setPen(QPen(QBrush(border), 1.0))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawPath(path)

        spec = QLinearGradient(r.left() + rad, 0, r.right() - rad, 0)
        spec.setColorAt(0.0, QColor(255, 255, 255, 0))
        spec.setColorAt(0.5, QColor(255, 255, 255, 80))
        spec.setColorAt(1.0, QColor(255, 255, 255, 0))
        p.setPen(QPen(QBrush(spec), 1.0))
        p.drawLine(QPointF(r.left() + rad, r.top() + 1.0),
                   QPointF(r.right() - rad, r.top() + 1.0))


class SettingRow(QWidget):
    """Ligne de réglage : titre + aide à gauche, contrôle à droite."""

    def __init__(self, title: str, control: QWidget | None = None,
                 hint: str | None = None, stacked: bool = False, parent=None):
        super().__init__(parent)
        self._title = QLabel(title)
        self._title.setObjectName("rowTitle")
        self._hint = QLabel(hint or "")
        self._hint.setObjectName("hint")
        self._hint.setWordWrap(True)
        self._hint.setVisible(bool(hint))

        text = QVBoxLayout()
        text.setSpacing(3)
        text.addWidget(self._title)
        text.addWidget(self._hint)

        if stacked:
            root = QVBoxLayout(self)
            root.setContentsMargins(0, 14, 0, 14)
            root.setSpacing(10)
            root.addLayout(text)
            if control is not None:
                root.addWidget(control)
        else:
            root = QHBoxLayout(self)
            root.setContentsMargins(0, 14, 0, 14)
            root.setSpacing(28)
            root.addLayout(text, 1)
            if control is not None:
                root.addWidget(control, 0, Qt.AlignmentFlag.AlignRight
                               | Qt.AlignmentFlag.AlignVCenter)

    def set_hint(self, text: str, tone: str = "") -> None:
        self._hint.setText(text)
        self._hint.setVisible(bool(text))
        theme.set_tone(self._hint, tone)


class FadeStack(QStackedWidget):
    """Pile de pages avec fondu à chaque changement."""

    animate = True  # désactivable depuis les réglages

    def set_index(self, index: int) -> None:
        if index == self.currentIndex() or not (0 <= index < self.count()):
            return
        self.setCurrentIndex(index)
        if not self.animate:
            return
        page = self.currentWidget()
        effect = QGraphicsOpacityEffect(page)
        effect.setOpacity(0.0)
        page.setGraphicsEffect(effect)
        anim = QPropertyAnimation(effect, b"opacity", page)
        anim.setDuration(240)
        anim.setStartValue(0.0)
        anim.setEndValue(1.0)
        anim.setEasingCurve(QEasingCurve(QEasingCurve.Type.OutCubic))
        anim.finished.connect(lambda pg=page: pg.setGraphicsEffect(None))
        anim.start(QAbstractAnimation.DeletionPolicy.DeleteWhenStopped)
