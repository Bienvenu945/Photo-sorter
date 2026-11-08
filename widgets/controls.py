"""Contrôles en verre : bascule, segments, liste, champ, curseur, boutons.

Tous les contrôles de réglage exposent la même interface :
    value() / set_value(v) / signal changed(valeur)
ce qui permet de les relier au SettingsStore avec `bind()`.
"""
from __future__ import annotations

import math

from PySide6.QtCore import (QEasingCurve, QPointF, QRectF, QSize, Qt,
                            QVariantAnimation, Signal)
from PySide6.QtGui import (QBrush, QColor, QFont, QFontMetrics, QLinearGradient,
                           QPainter, QPen)
from PySide6.QtWidgets import (QAbstractButton, QAbstractSpinBox, QComboBox,
                               QHBoxLayout, QLineEdit, QListView, QSizePolicy,
                               QSlider, QSpinBox, QWidget)

import theme
from widgets import icons

AA = QPainter.RenderHint.Antialiasing


def _animation(parent, ms: int, curve=QEasingCurve.Type.OutCubic) -> QVariantAnimation:
    anim = QVariantAnimation(parent)
    anim.setDuration(ms)
    anim.setEasingCurve(QEasingCurve(curve))
    return anim


def bind(store, key: str, ctrl) -> None:
    """Relie un contrôle à un réglage (dans les deux sens)."""
    ctrl.set_value(store.get(key))
    ctrl.changed.connect(lambda v, k=key: store.set(k, v))

    def on_store(changed_key: str) -> None:
        if changed_key == key and ctrl.value() != store.get(key):
            ctrl.set_value(store.get(key))

    store.changed.connect(on_store)


def hbox(*widgets: QWidget, spacing: int = 10) -> QWidget:
    box = QWidget()
    lay = QHBoxLayout(box)
    lay.setContentsMargins(0, 0, 0, 0)
    lay.setSpacing(spacing)
    for w in widgets:
        lay.addWidget(w)
    return box


class WheelGuard:
    """La molette ne modifie le contrôle que s'il a le focus (défilement sûr)."""

    def wheelEvent(self, event) -> None:
        if self.hasFocus():
            super().wheelEvent(event)
        else:
            event.ignore()


# ----------------------------------------------------------------------
# Bascule
# ----------------------------------------------------------------------

class Toggle(QAbstractButton):
    changed = Signal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.TabFocus)
        self.setFixedSize(52, 30)
        self._pos = 0.0
        self._anim = _animation(self, 220, QEasingCurve.Type.OutCubic)
        self._anim.valueChanged.connect(self._on_anim)
        self.toggled.connect(self._on_toggled)

    def _animate_to(self, target: float) -> None:
        self._anim.stop()
        if not self.isVisible():
            self._pos = target
            self.update()
            return
        self._anim.setStartValue(self._pos)
        self._anim.setEndValue(target)
        self._anim.start()

    def _on_anim(self, value) -> None:
        self._pos = float(value)
        self.update()

    def _on_toggled(self, on: bool) -> None:
        self._animate_to(1.0 if on else 0.0)
        self.changed.emit(on)

    def value(self) -> bool:
        return self.isChecked()

    def set_value(self, value) -> None:
        value = bool(value)
        if value == self.isChecked():
            return
        was = self.blockSignals(True)
        self.setChecked(value)
        self.blockSignals(was)
        self._animate_to(1.0 if value else 0.0)

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.setRenderHint(AA)
        if not self.isEnabled():
            p.setOpacity(0.4)
        pal = theme.current()
        w, h, t = self.width(), self.height(), self._pos
        track = QRectF(1, 1, w - 2, h - 2)
        radius = track.height() / 2

        p.setPen(QPen(theme.ov(46), 1))
        p.setBrush(theme.ov(28))
        p.drawRoundedRect(track, radius, radius)
        if t > 0.0:
            grad = QLinearGradient(track.left(), 0, track.right(), 0)
            grad.setColorAt(0, theme.qcolor(pal.accent_a, t))
            grad.setColorAt(1, theme.qcolor(pal.accent_b, t))
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QBrush(grad))
            p.drawRoundedRect(track, radius, radius)

        # bouton : s'étire légèrement quand on appuie (effet « goutte »)
        d = h - 10.0
        kw = d + (5.0 if self.isDown() else 0.0)
        x = 5.0 + t * (w - 10.0 - kw)
        knob = QRectF(x, 5.0, kw, d)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(0, 0, 0, 55))
        p.drawRoundedRect(knob.translated(0, 1.2), d / 2, d / 2)
        kg = QLinearGradient(0, knob.top(), 0, knob.bottom())
        kg.setColorAt(0, QColor(255, 255, 255, 255))
        kg.setColorAt(1, QColor(228, 232, 245, 255))
        p.setBrush(QBrush(kg))
        p.drawRoundedRect(knob, d / 2, d / 2)

        if self.hasFocus():
            p.setPen(QPen(theme.qcolor(pal.accent_a, 0.7), 1.5))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawRoundedRect(track.adjusted(-1, -1, 1, 1), radius + 1, radius + 1)


# ----------------------------------------------------------------------
# Segments (indicateur liquide)
# ----------------------------------------------------------------------

class Segmented(QWidget):
    changed = Signal(object)
    PAD = 4
    HEIGHT = 38

    def __init__(self, items, parent=None):
        super().__init__(parent)
        self._items = [(str(label), value) for label, value in items]
        self._index = 0
        self._pos = 0.0
        self._hover = -1
        self.setMouseTracking(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.TabFocus)
        self.setFont(theme.ui_font(9.5, QFont.Weight.Medium))
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self._anim = _animation(self, 340, QEasingCurve.Type.OutBack)
        curve = QEasingCurve(QEasingCurve.Type.OutBack)
        curve.setOvershoot(0.9)
        self._anim.setEasingCurve(curve)
        self._anim.valueChanged.connect(self._on_anim)

    # -- géométrie -----------------------------------------------------
    def _widths(self) -> list[int]:
        fm = QFontMetrics(self.font())
        return [max(62, fm.horizontalAdvance(label) + 32)
                for label, _ in self._items]

    def _lefts(self) -> list[int]:
        xs, x = [], self.PAD
        for w in self._widths():
            xs.append(x)
            x += w
        return xs

    def sizeHint(self) -> QSize:
        return QSize(sum(self._widths()) + 2 * self.PAD, self.HEIGHT)

    def minimumSizeHint(self) -> QSize:
        return self.sizeHint()

    def _indicator(self) -> tuple[float, float]:
        ws, xs = self._widths(), self._lefts()
        n = len(ws)
        if n == 0:
            return 0.0, 0.0
        if n == 1:
            return float(xs[0]), float(ws[0])
        i = max(0, min(n - 2, int(math.floor(self._pos))))
        t = self._pos - i
        return (xs[i] + (xs[i + 1] - xs[i]) * t,
                ws[i] + (ws[i + 1] - ws[i]) * t)

    def _index_at(self, x: float) -> int:
        ws, xs = self._widths(), self._lefts()
        for i, (left, width) in enumerate(zip(xs, ws)):
            if left <= x < left + width:
                return i
        return -1

    # -- valeur --------------------------------------------------------
    def value(self):
        return self._items[self._index][1] if self._items else None

    def set_value(self, value) -> None:
        idx = next((i for i, (_, v) in enumerate(self._items) if v == value), -1)
        if idx < 0:
            self._items.append((str(value), value))
            idx = len(self._items) - 1
            self.updateGeometry()
        self._select(idx, user=False)

    def _select(self, idx: int, user: bool) -> None:
        if idx == self._index and self._pos == float(idx):
            return
        changed = idx != self._index
        self._index = idx
        self._anim.stop()
        if not self.isVisible():
            self._pos = float(idx)
            self.update()
            if user and changed:
                self.changed.emit(self.value())
            return
        self._anim.setStartValue(self._pos)
        self._anim.setEndValue(float(idx))
        self._anim.start()
        if user and changed:
            self.changed.emit(self.value())

    def _on_anim(self, value) -> None:
        self._pos = float(value)
        self.update()

    # -- interaction ---------------------------------------------------
    def mouseMoveEvent(self, event) -> None:
        idx = self._index_at(event.position().x())
        if idx != self._hover:
            self._hover = idx
            self.update()

    def leaveEvent(self, _event) -> None:
        self._hover = -1
        self.update()

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            idx = self._index_at(event.position().x())
            if idx >= 0:
                self._select(idx, user=True)

    def keyPressEvent(self, event) -> None:
        if event.key() in (Qt.Key.Key_Left, Qt.Key.Key_Up) and self._index > 0:
            self._select(self._index - 1, user=True)
        elif event.key() in (Qt.Key.Key_Right, Qt.Key.Key_Down) \
                and self._index < len(self._items) - 1:
            self._select(self._index + 1, user=True)
        else:
            super().keyPressEvent(event)

    # -- peinture ------------------------------------------------------
    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.setRenderHint(AA)
        if not self.isEnabled():
            p.setOpacity(0.4)
        pal = theme.current()
        w, h = self.width(), self.height()

        track = QRectF(0.5, 0.5, w - 1, h - 1)
        p.setPen(QPen(theme.ov(34), 1))
        p.setBrush(theme.ov(18))
        p.drawRoundedRect(track, h / 2, h / 2)

        x, iw = self._indicator()
        ir = QRectF(x, self.PAD, iw, h - 2 * self.PAD)
        grad = QLinearGradient(ir.left(), 0, ir.right(), 0)
        grad.setColorAt(0, theme.qcolor(pal.accent_a, 0.95))
        grad.setColorAt(1, theme.qcolor(pal.accent_b, 0.95))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(grad))
        p.drawRoundedRect(ir, ir.height() / 2, ir.height() / 2)
        sheen = QLinearGradient(0, ir.top(), 0, ir.bottom())
        sheen.setColorAt(0, QColor(255, 255, 255, 70))
        sheen.setColorAt(0.55, QColor(255, 255, 255, 0))
        p.setBrush(QBrush(sheen))
        p.drawRoundedRect(ir, ir.height() / 2, ir.height() / 2)

        p.setFont(self.font())
        ink = QColor(pal.ink)
        xs, ws = self._lefts(), self._widths()
        for i, (label, _) in enumerate(self._items):
            near = max(0.0, 1.0 - abs(self._pos - i))
            base = theme.fg(235 if i == self._hover else 175)
            p.setPen(theme.mix(base, ink, near))
            p.drawText(QRectF(xs[i], 0, ws[i], h),
                       Qt.AlignmentFlag.AlignCenter, label)

        if self.hasFocus():
            p.setPen(QPen(theme.qcolor(pal.accent_a, 0.6), 1.5))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawRoundedRect(track.adjusted(-1, -1, 1, 1), h / 2 + 1, h / 2 + 1)


# ----------------------------------------------------------------------
# Liste déroulante
# ----------------------------------------------------------------------

class GlassCombo(WheelGuard, QComboBox):
    changed = Signal(object)

    def __init__(self, items=(), width: int = 260, parent=None):
        super().__init__(parent)
        self.setView(QListView())
        self.setFixedHeight(40)
        self.setMinimumWidth(width)
        self.setMaxVisibleItems(10)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
        for label, value in items:
            self.addItem(label, value)
        self.activated.connect(lambda _i: self.changed.emit(self.currentData()))

    def value(self):
        return self.currentData()

    def set_value(self, value) -> None:
        was = self.blockSignals(True)
        i = self.findData(value)
        if i < 0 and value:
            self.addItem(str(value), value)
            i = self.count() - 1
        self.setCurrentIndex(max(i, 0))
        self.blockSignals(was)
        self.update()

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.setRenderHint(AA)
        if not self.isEnabled():
            p.setOpacity(0.4)
        pal = theme.current()
        w, h = self.width(), self.height()
        r = QRectF(0.5, 0.5, w - 1, h - 1)
        active = self.hasFocus() or self.view().isVisible()
        hover = self.underMouse()

        p.setBrush(theme.ov(38 if hover else 26))
        if active:
            p.setPen(QPen(theme.qcolor(pal.accent_a, 0.85), 1))
        else:
            p.setPen(QPen(theme.ov(38), 1))
        p.drawRoundedRect(r, 11, 11)

        p.setFont(theme.ui_font(10))
        p.setPen(theme.fg())
        text = QFontMetrics(p.font()).elidedText(
            self.currentText(), Qt.TextElideMode.ElideRight, w - 52)
        p.drawText(QRectF(15, 0, w - 52, h),
                   Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, text)

        cx, cy = w - 21.0, h / 2.0
        p.setPen(QPen(theme.fg(170), 1.8,
                      Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap,
                      Qt.PenJoinStyle.RoundJoin))
        a = QPointF(cx - 4.5, cy - 2.0)
        b = QPointF(cx, cy + 2.5)
        c = QPointF(cx + 4.5, cy - 2.0)
        p.drawLine(a, b)
        p.drawLine(b, c)


# ----------------------------------------------------------------------
# Champ texte
# ----------------------------------------------------------------------

class GlassLine(QLineEdit):
    changed = Signal(object)

    def __init__(self, placeholder: str = "", width: int = 0, parent=None):
        super().__init__(parent)
        self.setPlaceholderText(placeholder)
        self.setMinimumHeight(42)
        if width:
            self.setFixedWidth(width)
        self.textChanged.connect(lambda text: self.changed.emit(text.strip()))

    def value(self) -> str:
        return self.text().strip()

    def set_value(self, value) -> None:
        was = self.blockSignals(True)
        self.setText(str(value))
        self.blockSignals(was)


# ----------------------------------------------------------------------
# Curseur + valeur
# ----------------------------------------------------------------------

class GlassSlider(WheelGuard, QSlider):
    def __init__(self, parent=None):
        super().__init__(Qt.Orientation.Horizontal, parent)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(30)


class GlassSpin(WheelGuard, QSpinBox):
    pass


class SliderSpin(QWidget):
    changed = Signal(object)

    def __init__(self, lo: int, hi: int, suffix: str = "", special: str = "",
                 snap: int = 1, width: int = 400, parent=None):
        super().__init__(parent)
        self._lo, self._hi, self._snap = lo, hi, max(1, snap)
        self.setFixedWidth(width)

        self.slider = GlassSlider()
        self.slider.setRange(lo, hi)
        self.slider.setSingleStep(self._snap)
        self.slider.setPageStep(self._snap * 5)

        self.spin = GlassSpin()
        self.spin.setRange(lo, hi)
        self.spin.setFixedWidth(118)
        self.spin.setMinimumHeight(40)
        self.spin.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.spin.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
        self.spin.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        if suffix:
            self.spin.setSuffix(suffix)
        if special:
            self.spin.setSpecialValueText(special)

        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(14)
        lay.addWidget(self.slider, 1)
        lay.addWidget(self.spin, 0)

        self.slider.valueChanged.connect(self._on_slider)
        self.spin.valueChanged.connect(self._on_spin)

    def _on_slider(self, raw: int) -> None:
        v = self._lo + round((raw - self._lo) / self._snap) * self._snap
        v = max(self._lo, min(self._hi, v))
        if v != raw:
            was = self.slider.blockSignals(True)
            self.slider.setValue(v)
            self.slider.blockSignals(was)
        was = self.spin.blockSignals(True)
        self.spin.setValue(v)
        self.spin.blockSignals(was)
        self.changed.emit(v)

    def _on_spin(self, v: int) -> None:
        was = self.slider.blockSignals(True)
        self.slider.setValue(v)
        self.slider.blockSignals(was)
        self.changed.emit(v)

    def value(self) -> int:
        return self.spin.value()

    def set_value(self, value) -> None:
        v = max(self._lo, min(self._hi, int(value)))
        for w in (self.slider, self.spin):
            was = w.blockSignals(True)
            w.setValue(v)
            w.blockSignals(was)


# ----------------------------------------------------------------------
# Boutons
# ----------------------------------------------------------------------

class GlassButton(QAbstractButton):
    """Bouton en verre. variant : default, primary, danger, ghost, chip."""

    def __init__(self, text: str = "", variant: str = "default",
                 icon: str | None = None, parent=None):
        super().__init__(parent)
        self._variant = variant
        self._icon = icon
        self._active = False
        self._hv = 0.0
        self.setText(text)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.TabFocus)
        self.setFont(theme.ui_font(10, QFont.Weight.Medium))
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
        self._anim = _animation(self, 160)
        self._anim.valueChanged.connect(self._on_anim)

    # -- apparence -----------------------------------------------------
    def set_icon(self, name: str | None) -> None:
        self._icon = name
        self.updateGeometry()
        self.update()

    def set_variant(self, variant: str) -> None:
        self._variant = variant
        self.updateGeometry()
        self.update()

    def set_active(self, on: bool) -> None:
        if on != self._active:
            self._active = on
            self.update()

    def _height(self) -> int:
        return {"primary": 48, "chip": 34}.get(self._variant, 40)

    def _pad(self) -> int:
        return {"primary": 28, "chip": 16}.get(self._variant, 18)

    def sizeHint(self) -> QSize:
        h = self._height()
        text = self.text()
        if not text and self._icon:
            return QSize(h, h)
        w = QFontMetrics(self.font()).horizontalAdvance(text) + 2 * self._pad()
        if self._icon:
            w += 26
        return QSize(w, h)

    def minimumSizeHint(self) -> QSize:
        return self.sizeHint()

    # -- survol --------------------------------------------------------
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

    # -- peinture ------------------------------------------------------
    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.setRenderHint(AA)
        if not self.isEnabled():
            p.setOpacity(0.38)
        pal = theme.current()
        v, hv = self._variant, self._hv
        w, h = self.width(), self.height()
        if self.isDown():
            p.translate(0, 1)
        r = QRectF(0.5, 0.5, w - 1, h - 1)
        radius = h / 2 if v in ("chip", "primary") else 12

        border = QLinearGradient(0, r.top(), 0, r.bottom())
        text_color = theme.fg()

        if v == "primary":
            fill = QLinearGradient(r.left(), 0, r.right(), 0)
            boost = 0.10 * hv
            fill.setColorAt(0, theme.mix(pal.accent_a, "#ffffff", boost))
            fill.setColorAt(1, theme.mix(pal.accent_b, "#ffffff", boost))
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QBrush(fill))
            p.drawRoundedRect(r, radius, radius)
            sheen = QLinearGradient(0, r.top(), 0, r.bottom())
            sheen.setColorAt(0, QColor(255, 255, 255, 80))
            sheen.setColorAt(0.6, QColor(255, 255, 255, 0))
            p.setBrush(QBrush(sheen))
            p.drawRoundedRect(r, radius, radius)
            text_color = QColor(pal.ink)
        elif v == "danger":
            p.setBrush(QColor(255, 99, 99, int(26 + 34 * hv)))
            p.setPen(QPen(QColor(255, 130, 125, int(110 + 90 * hv)), 1))
            p.drawRoundedRect(r, radius, radius)
            text_color = QColor(255, 160, 154)
        elif v == "ghost":
            p.setBrush(theme.ov(int(22 * hv)))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawRoundedRect(r, radius, radius)
            text_color = theme.fg(int(165 + 80 * hv))
        else:  # default, chip
            if v == "chip" and self._active:
                p.setBrush(theme.qcolor(pal.accent_a, 0.18))
                border.setColorAt(0, theme.qcolor(pal.accent_a, 0.95))
                border.setColorAt(1, theme.qcolor(pal.accent_b, 0.75))
                text_color = theme.strong()
            else:
                p.setBrush(theme.ov(int(20 + 24 * hv)))
                border.setColorAt(0, theme.ov(int(70 + 60 * hv)))
                border.setColorAt(1, theme.ov(int(22 + 40 * hv)))
            p.setPen(QPen(QBrush(border), 1))
            p.drawRoundedRect(r, radius, radius)

        # contenu : icône + texte centrés
        p.setFont(self.font())
        fm = QFontMetrics(self.font())
        text = self.text()
        tw = fm.horizontalAdvance(text) if text else 0
        icon_px = icons.pixmap(self._icon, text_color.name(), 17,
                               self.devicePixelRatioF()) if self._icon else None
        has_icon = icon_px is not None and not icon_px.isNull()
        content = (17 if has_icon else 0) + (8 if has_icon and tw else 0) + tw
        x = (w - content) / 2
        if has_icon:
            p.setOpacity(p.opacity() * text_color.alphaF())
            p.drawPixmap(int(x), int((h - 17) / 2), icon_px)
            p.setOpacity(1.0 if self.isEnabled() else 0.38)
            x += 17 + (8 if tw else 0)
        if tw:
            p.setPen(text_color)
            p.drawText(QRectF(x, 0, tw + 2, h),
                       Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, text)

        if self.hasFocus():
            p.setPen(QPen(theme.qcolor(pal.accent_a, 0.75), 1.5))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawRoundedRect(r.adjusted(-1, -1, 1, 1), radius + 1, radius + 1)
