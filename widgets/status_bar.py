"""Zone E : barre inférieure (état, progression, compteur, raccourcis contextuels)."""
from __future__ import annotations

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QBrush, QLinearGradient, QPainter
from PySide6.QtWidgets import QHBoxLayout, QLabel, QWidget

import theme


class ProgressStrip(QWidget):
    """Fine barre de progression en dégradé d'accent."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setFixedHeight(8)
        self._fraction = 0.0

    def set_fraction(self, value: float) -> None:
        self._fraction = max(0.0, min(1.0, float(value)))
        self.update()

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        pal = theme.current()
        r = QRectF(0, 0, self.width(), self.height())
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(theme.ov(30))
        p.drawRoundedRect(r, 4, 4)
        if self._fraction > 0:
            w = max(8.0, r.width() * self._fraction)
            g = QLinearGradient(0, 0, w, 0)
            g.setColorAt(0, theme.qcolor(pal.accent_a))
            g.setColorAt(1, theme.qcolor(pal.accent_b))
            p.setBrush(QBrush(g))
            p.drawRoundedRect(QRectF(0, 0, w, r.height()), 4, 4)


class StatusBar(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setFixedHeight(34)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(6, 0, 6, 0)
        lay.setSpacing(16)
        self.state = QLabel("Prêt")
        self.state.setObjectName("hint")
        self.strip = ProgressStrip()
        self.strip.setMinimumWidth(160)
        self.count = QLabel("")
        self.count.setObjectName("progress")
        self.hints = QLabel("")
        self.hints.setObjectName("muted")
        lay.addWidget(self.state)
        lay.addWidget(self.strip, 1)
        lay.addWidget(self.count)
        lay.addWidget(self.hints)

    def update_state(self, state: str, done: int, total: int, hints: str = "") -> None:
        """``done``/``total`` = photos traitées / photos de la session (0 si aucune session)."""
        self.state.setText(state)
        self.strip.set_fraction(done / total if total else 0.0)
        self.count.setText(f"{done} / {total}" if total else "")
        self.hints.setText(hints)
