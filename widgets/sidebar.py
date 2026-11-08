"""Barre latérale : navigation avec indicateur liquide + signature."""
from __future__ import annotations

from PySide6.QtCore import QEasingCurve, QRectF, Qt, QVariantAnimation, Signal
from PySide6.QtGui import QBrush, QColor, QFont, QLinearGradient, QPainter, QPen
from PySide6.QtWidgets import QAbstractButton, QLabel, QVBoxLayout, QWidget

import theme
from config import AUTHOR, YEAR
from widgets import icons
from widgets.controls import GlassButton
from widgets.glass import GlassCard


class NavButton(QAbstractButton):
    def __init__(self, icon: str, text: str, parent=None):
        super().__init__(parent)
        self._icon = icon
        self.setText(text)
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.TabFocus)
        self.setFixedHeight(Sidebar.BTN_H)
        self.setFont(theme.ui_font(10.5, QFont.Weight.Medium))
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
        self._hv = 0.0
        self._anim = QVariantAnimation(self)
        self._anim.setDuration(160)
        self._anim.valueChanged.connect(self._on_anim)

    def _fade(self, target: float) -> None:
        self._anim.stop()
        self._anim.setStartValue(self._hv)
        self._anim.setEndValue(target)
        self._anim.start()

    def _on_anim(self, value) -> None:
        self._hv = float(value)
        self.update()

    def enterEvent(self, event) -> None:
        self._fade(1.0)
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        self._fade(0.0)
        super().leaveEvent(event)

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        pal = theme.current()
        w, h = self.width(), self.height()
        checked = self.isChecked()

        if not checked and self._hv > 0:
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(theme.ov(int(16 * self._hv)))
            p.drawRoundedRect(QRectF(0, 0, w, h), 14, 14)

        color = QColor(pal.accent_a) if checked else theme.fg(int(150 + 90 * self._hv))
        pm = icons.pixmap(self._icon, color.name(), 20, self.devicePixelRatioF())
        if not pm.isNull():
            p.drawPixmap(18, int((h - 20) / 2), pm)

        p.setFont(self.font())
        p.setPen(theme.strong() if checked
                 else theme.fg(int(170 + 70 * self._hv)))
        p.drawText(QRectF(52, 0, w - 60, h),
                   Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                   self.text())

        if self.hasFocus():
            p.setPen(QPen(theme.qcolor(pal.accent_a, 0.6), 1.5))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawRoundedRect(QRectF(1, 1, w - 2, h - 2), 14, 14)


class Sidebar(GlassCard):
    currentChanged = Signal(int)
    aboutRequested = Signal()
    BTN_H = 46
    GAP = 4
    TOP = 14
    SIDE = 10

    def __init__(self, entries, parent=None):
        super().__init__(parent=parent, radius=24.0)
        self.setFixedWidth(220)
        self._buttons: list[NavButton] = []
        self._current = 0
        self._ind_y = float(self.TOP)

        lay = self.layout()
        lay.setContentsMargins(self.SIDE, self.TOP, self.SIDE, 16)
        lay.setSpacing(self.GAP)

        for i, (icon, label) in enumerate(entries):
            b = NavButton(icon, label)
            b.clicked.connect(lambda _=False, idx=i: self.set_current(idx))
            lay.addWidget(b)
            self._buttons.append(b)
        self._buttons[0].setChecked(True)
        lay.addStretch(1)

        foot = QWidget()
        fl = QVBoxLayout(foot)
        fl.setContentsMargins(10, 0, 10, 0)
        fl.setSpacing(1)
        by = QLabel("Conçu par")
        by.setObjectName("muted")
        sig = QLabel(AUTHOR)
        sig.setObjectName("signature")
        sig.setFont(theme.serif_font(14.5, italic=True))
        year = QLabel("© %s" % YEAR)
        year.setObjectName("muted")
        about = GlassButton("À propos", "ghost", "info")
        about.clicked.connect(self.aboutRequested)
        fl.addWidget(by)
        fl.addWidget(sig)
        fl.addWidget(year)
        fl.addSpacing(6)
        fl.addWidget(about)
        lay.addWidget(foot)

        self._anim = QVariantAnimation(self)
        self._anim.setDuration(380)
        curve = QEasingCurve(QEasingCurve.Type.OutBack)
        curve.setOvershoot(0.7)
        self._anim.setEasingCurve(curve)
        self._anim.valueChanged.connect(self._on_anim)

    def _target_y(self, index: int) -> float:
        return float(self.TOP + index * (self.BTN_H + self.GAP))

    def _on_anim(self, value) -> None:
        self._ind_y = float(value)
        self.update()

    def current(self) -> int:
        return self._current

    def set_current(self, index: int) -> None:
        if not (0 <= index < len(self._buttons)):
            return
        for i, b in enumerate(self._buttons):
            b.setChecked(i == index)
        if index != self._current:
            self._current = index
            self._anim.stop()
            self._anim.setStartValue(self._ind_y)
            self._anim.setEndValue(self._target_y(index))
            self._anim.start()
            self.currentChanged.emit(index)

    def paintEvent(self, event) -> None:
        super().paintEvent(event)
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        pal = theme.current()
        r = QRectF(self.SIDE, self._ind_y, self.width() - 2 * self.SIDE, self.BTN_H)
        fill = QLinearGradient(r.left(), 0, r.right(), 0)
        fill.setColorAt(0, theme.qcolor(pal.accent_a, 0.22))
        fill.setColorAt(1, theme.qcolor(pal.accent_b, 0.12))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(fill))
        p.drawRoundedRect(r, 14, 14)
        edge = QLinearGradient(0, r.top(), 0, r.bottom())
        edge.setColorAt(0, theme.qcolor(pal.accent_a, 0.65))
        edge.setColorAt(1, theme.qcolor(pal.accent_b, 0.25))
        p.setPen(QPen(QBrush(edge), 1))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(r.adjusted(0.5, 0.5, -0.5, -0.5), 14, 14)
        # barre lumineuse à gauche
        bar = QRectF(r.left() + 5, r.top() + 12, 3, r.height() - 24)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(theme.qcolor(pal.accent_a, 0.95))
        p.drawRoundedRect(bar, 1.5, 1.5)
