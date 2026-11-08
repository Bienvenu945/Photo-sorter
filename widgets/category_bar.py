"""Boutons de catégories en verre, générés dynamiquement depuis la configuration."""
from __future__ import annotations

from PySide6.QtCore import QRectF, QSize, Qt, QVariantAnimation
from PySide6.QtGui import QColor, QFont, QFontMetrics, QKeySequence, QLinearGradient, QBrush, QPainter, QPen
from PySide6.QtWidgets import QAbstractButton, QGridLayout, QSizePolicy, QWidget
from PySide6.QtCore import Signal

import theme

COLUMNS = 4


class CatButton(QAbstractButton):
    """Pastille de verre : point de couleur + nom + touche de raccourci."""

    def __init__(self, category, parent=None) -> None:
        super().__init__(parent)
        self._color = category.color
        key = QKeySequence(category.shortcut).toString(QKeySequence.SequenceFormat.NativeText)
        self._key = key or category.shortcut
        self.setText(category.name)
        self.setFixedHeight(48)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
        self.setFont(theme.ui_font(10.5, QFont.Weight.Medium))
        self.setToolTip(f"{category.name}  ({self._key})")
        self._hv = 0.0
        self._anim = QVariantAnimation(self)
        self._anim.setDuration(160)
        self._anim.valueChanged.connect(self._on_anim)

    def sizeHint(self) -> QSize:
        return QSize(QFontMetrics(self.font()).horizontalAdvance(self.text()) + 96, 48)

    def _on_anim(self, v) -> None:
        self._hv = float(v)
        self.update()

    def _fade(self, target: float) -> None:
        self._anim.stop()
        self._anim.setStartValue(self._hv)
        self._anim.setEndValue(target)
        self._anim.start()

    def enterEvent(self, e) -> None:
        self._fade(1.0)
        super().enterEvent(e)

    def leaveEvent(self, e) -> None:
        self._fade(0.0)
        super().leaveEvent(e)

    def paintEvent(self, _e) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h, hv = self.width(), self.height(), self._hv
        if self.isDown():
            p.translate(0, 1)
        r = QRectF(0.5, 0.5, w - 1, h - 1)
        p.setBrush(theme.ov(int(20 + 26 * hv)))
        border = QLinearGradient(0, r.top(), 0, r.bottom())
        border.setColorAt(0, theme.qcolor(self._color, 0.45 + 0.4 * hv))
        border.setColorAt(1, theme.ov(int(24 + 40 * hv)))
        p.setPen(QPen(QBrush(border), 1))
        p.drawRoundedRect(r, 15, 15)
        # point de couleur
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(self._color))
        p.drawEllipse(QRectF(16, h / 2 - 5, 10, 10))
        # nom
        p.setFont(self.font())
        p.setPen(theme.ov(235))
        fm = QFontMetrics(self.font())
        name = fm.elidedText(self.text(), Qt.TextElideMode.ElideRight, w - 96)
        p.drawText(QRectF(36, 0, w - 90, h), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, name)
        # badge raccourci
        bf = theme.ui_font(9, QFont.Weight.DemiBold)
        bw = max(26, QFontMetrics(bf).horizontalAdvance(self._key) + 14)
        badge = QRectF(w - bw - 12, h / 2 - 11, bw, 22)
        p.setBrush(theme.ov(30))
        p.setPen(QPen(theme.ov(50), 1))
        p.drawRoundedRect(badge, 8, 8)
        p.setFont(bf)
        p.setPen(theme.fg(220))
        p.drawText(badge, Qt.AlignmentFlag.AlignCenter, self._key)


class CategoryBar(QWidget):
    category_chosen = Signal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._grid = QGridLayout(self)
        self._grid.setContentsMargins(0, 0, 0, 0)
        self._grid.setSpacing(10)

    def set_categories(self, categories) -> None:
        while self._grid.count():
            item = self._grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        for i, c in enumerate(categories):
            b = CatButton(c)
            b.clicked.connect(lambda _=False, cid=c.id: self.category_chosen.emit(cid))
            self._grid.addWidget(b, i // COLUMNS, i % COLUMNS)
        for col in range(COLUMNS):
            self._grid.setColumnStretch(col, 1)
