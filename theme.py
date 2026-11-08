"""Thème HyperOS-inspired (défaut, clair, hacker) + palettes « verre » : palettes, polices, feuille de style Qt."""
from __future__ import annotations

import re
from dataclasses import dataclass, replace

from PySide6.QtGui import QColor, QFont, QFontDatabase, QPalette

TEXT = "#eef0f8"


@dataclass(frozen=True)
class Palette:
    key: str
    label: str
    bg_top: str
    bg_bottom: str
    accent_a: str
    accent_b: str
    ink: str            # couleur du texte posé sur l'accent
    # (couleur, x, y, rayon, dérive x, dérive y, vitesse, phase, opacité)
    blobs: tuple
    flat: bool = False          # surfaces plates (HyperOS) au lieu de verre translucide
    light: bool = False
    fg: str = "#eef0f8"         # texte principal
    strong: str = "#ffffff"     # titres / texte accentué
    surface: str = "#101324"    # panneaux
    card: str = "#161a2e"       # cartes secondaires


PALETTES = {
    "hyperos": Palette(
        "hyperos", "HyperOS (sombre)", "#0B0E14", "#0B0E14", "#75B9FF", "#A78BFA", "#0B1220", (),
        flat=True, fg="#F2F5FA", strong="#FFFFFF", surface="#151B25", card="#1D2532"),
    "hyperos_light": Palette(
        "hyperos_light", "HyperOS (clair)", "#EEF2F8", "#E6ECF5", "#2F7BFF", "#7C5CFA", "#FFFFFF", (),
        flat=True, light=True, fg="#2A3342", strong="#0B0E14", surface="#FFFFFF", card="#F4F7FB"),
    "hacker": Palette(
        "hacker", "Hacker (vert néon)", "#020805", "#010403", "#00FF9C", "#00C46A", "#00140B", (),
        flat=True, fg="#C8FFE6", strong="#E8FFF4", surface="#07140F", card="#0B1E16"),
    "aurora": Palette(
        "aurora", "Aurore", "#0a0d1e", "#070912",
        "#67e8f9", "#a78bfa", "#0b1020",
        ((("#6a5cff"), 0.16, 0.18, 0.60, 0.10, 0.08, 0.20, 0.0, 0.62),
         (("#12c8e6"), 0.88, 0.28, 0.52, 0.08, 0.10, 0.17, 2.0, 0.44),
         (("#e0489b"), 0.72, 0.98, 0.58, 0.10, 0.06, 0.15, 4.0, 0.40),
         (("#3b82f6"), 0.08, 0.92, 0.48, 0.07, 0.08, 0.22, 1.0, 0.34))),
    "gold": Palette(
        "gold", "Or", "#100e0b", "#09080a",
        "#ecd49a", "#c9a45c", "#17130b",
        ((("#c9a45c"), 0.18, 0.20, 0.58, 0.10, 0.08, 0.18, 0.0, 0.52),
         (("#8a5a2b"), 0.88, 0.34, 0.52, 0.08, 0.10, 0.16, 2.0, 0.44),
         (("#e7c987"), 0.68, 0.98, 0.50, 0.10, 0.06, 0.14, 4.0, 0.26),
         (("#5b4a8a"), 0.08, 0.92, 0.50, 0.07, 0.08, 0.21, 1.0, 0.34))),
    "ocean": Palette(
        "ocean", "Océan", "#05101b", "#040a13",
        "#5eead4", "#38bdf8", "#04141d",
        ((("#0ea5e9"), 0.16, 0.20, 0.60, 0.10, 0.08, 0.19, 0.0, 0.58),
         (("#10b981"), 0.88, 0.30, 0.50, 0.08, 0.10, 0.17, 2.0, 0.40),
         (("#6366f1"), 0.70, 0.98, 0.56, 0.10, 0.06, 0.15, 4.0, 0.40),
         (("#22d3ee"), 0.08, 0.92, 0.46, 0.07, 0.08, 0.22, 1.0, 0.30))),
}
PALETTE_CHOICES = [(p.label, p.key) for p in PALETTES.values()]

_current = PALETTES["hyperos"]


def current() -> Palette:
    return _current


def set_palette(key: str, accent: str | None = None) -> None:
    """Choisit la palette ; ``accent`` (ex. '#ff7a00') remplace les couleurs d'accent."""
    global _current
    base = PALETTES.get(key, PALETTES["hyperos"])
    if accent and QColor(accent).isValid():
        base = replace(base, accent_a=QColor(accent).name(),
                       accent_b=mix(accent, "#a78bfa", 0.45).name())
    _current = base


# ----------------------------------------------------------------------
# Couleurs
# ----------------------------------------------------------------------

def qcolor(value, alpha: float = 1.0) -> QColor:
    c = QColor(value)
    c.setAlphaF(max(0.0, min(1.0, alpha)))
    return c


def mix(a, b, t: float) -> QColor:
    """Mélange linéaire de deux couleurs (t = 0 → a, t = 1 → b)."""
    ca, cb = QColor(a), QColor(b)
    t = max(0.0, min(1.0, t))
    return QColor(
        int(ca.red() + (cb.red() - ca.red()) * t),
        int(ca.green() + (cb.green() - ca.green()) * t),
        int(ca.blue() + (cb.blue() - ca.blue()) * t),
        int(ca.alpha() + (cb.alpha() - ca.alpha()) * t))


def rgba(value, alpha: float) -> str:
    c = QColor(value)
    return "rgba(%d,%d,%d,%.3f)" % (c.red(), c.green(), c.blue(), alpha)


def popup_color() -> str:
    p = current()
    return "#ffffff" if p.light else mix(p.bg_top, "#ffffff", 0.07).name()


def fg(alpha: float = 255) -> QColor:
    """Texte courant du thème (alpha 0-255)."""
    c = QColor(current().fg)
    c.setAlpha(max(0, min(255, int(alpha))))
    return c


def strong(alpha: float = 255) -> QColor:
    """Texte accentué (blanc en sombre, quasi noir en clair)."""
    c = QColor(current().strong)
    c.setAlpha(max(0, min(255, int(alpha))))
    return c


def ov(alpha: float) -> QColor:
    """Voile pour fonds, filets et survols : blanc en thème sombre, encre en thème clair."""
    if current().light:
        return QColor(15, 23, 42, max(0, min(255, int(alpha * 0.7))))
    return QColor(255, 255, 255, max(0, min(255, int(alpha))))


def _ov_rgb() -> str:
    return "15,23,42" if current().light else "255,255,255"


# ----------------------------------------------------------------------
# Polices
# ----------------------------------------------------------------------

_UI_FAMILIES = ["Inter", "SF Pro Display", "Segoe UI Variable", "Segoe UI",
                "Noto Sans", "Cantarell", "DejaVu Sans"]
_SERIF_FAMILIES = ["Playfair Display", "Cormorant Garamond", "Georgia",
                   "DejaVu Serif", "serif"]


def ui_font(size: float = 10.0,
            weight: QFont.Weight = QFont.Weight.Normal) -> QFont:
    f = QFont()
    f.setFamilies(_UI_FAMILIES)
    f.setPointSizeF(size)
    f.setWeight(weight)
    return f


def serif_font(size: float, italic: bool = False, spacing: float = 0.0) -> QFont:
    f = QFont()
    f.setFamilies(_SERIF_FAMILIES)
    f.setPointSizeF(size)
    f.setItalic(italic)
    if spacing:
        f.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, spacing)
    return f


def mono_font(size: float = 10.0) -> QFont:
    f = QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont)
    f.setPointSizeF(size)
    return f


# ----------------------------------------------------------------------
# Feuille de style
# ----------------------------------------------------------------------

_QSS = """
QWidget { color: @TEXT@; }
QLabel { background: transparent; }
QLabel:disabled { color: rgba(238,240,248,0.30); }

QLabel#pageTitle { font-size: 26px; font-weight: 600; color: #ffffff; }
QLabel#pageSub { font-size: 13px; color: rgba(238,240,248,0.58); }
QLabel#cardTitle { font-size: 15px; font-weight: 600; color: #ffffff; }
QLabel#cardSub { font-size: 12px; color: rgba(238,240,248,0.52); }
QLabel#rowTitle { font-size: 13px; font-weight: 500; }
QLabel#hint { font-size: 12px; color: rgba(238,240,248,0.50); }
QLabel#hint[tone="ok"] { color: rgba(134,239,172,0.92); }
QLabel#hint[tone="warn"] { color: rgba(253,186,116,0.96); }
QLabel#hint[tone="error"] { color: rgba(252,165,165,0.96); }
QLabel#brand { font-size: 17px; font-weight: 600; color: #ffffff; }
QLabel#brandSub { font-size: 12px; color: rgba(238,240,248,0.50); }
QLabel#signature { color: @A@; }
QLabel#muted { font-size: 12px; color: rgba(238,240,248,0.48); }
QLabel#pill { font-size: 11px; color: rgba(238,240,248,0.72);
    background: rgba(255,255,255,0.07); border: 1px solid rgba(255,255,255,0.12);
    border-radius: 11px; padding: 3px 11px; }
QLabel#pill[tone="warn"] { color: rgba(253,186,116,0.98);
    border-color: rgba(253,186,116,0.45); background: rgba(253,186,116,0.10); }
QLabel#pill[tone="ok"] { color: rgba(134,239,172,0.95);
    border-color: rgba(134,239,172,0.35); background: rgba(134,239,172,0.08); }

QToolTip { background: @POP@; color: @TEXT@; border: 1px solid rgba(255,255,255,0.18);
    border-radius: 8px; padding: 6px 9px; }

QLineEdit, QSpinBox { background: rgba(255,255,255,0.065);
    border: 1px solid rgba(255,255,255,0.13); border-radius: 11px;
    padding: 8px 13px; selection-background-color: @A@; selection-color: @INK@; }
QLineEdit:hover, QSpinBox:hover { background: rgba(255,255,255,0.09); }
QLineEdit:focus, QSpinBox:focus { border: 1px solid @A_LINE@;
    background: rgba(255,255,255,0.10); }
QLineEdit:disabled, QSpinBox:disabled { background: rgba(255,255,255,0.03);
    color: rgba(238,240,248,0.30); border-color: rgba(255,255,255,0.06); }
QAbstractSpinBox QLineEdit { background: transparent; border: none; padding: 0; }
QLineEdit#preview { background: rgba(4,6,12,0.55); color: @A@;
    border: 1px solid rgba(255,255,255,0.10); padding: 10px 14px; }
QLineEdit#preview[error="true"] { color: #ff9a94;
    border-color: rgba(255,120,120,0.50); }

QComboBox QAbstractItemView, QListView { background: @POP@; color: @TEXT@;
    border: 1px solid rgba(255,255,255,0.16); border-radius: 10px; padding: 4px;
    selection-background-color: @A_SOFT@; selection-color: #ffffff; outline: 0; }
QComboBox QAbstractItemView::item { min-height: 30px; padding-left: 10px;
    border-radius: 7px; }

QSlider::groove:horizontal { height: 6px; background: rgba(255,255,255,0.11);
    border-radius: 3px; }
QSlider::sub-page:horizontal { border-radius: 3px;
    background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 @A@, stop:1 @B@); }
QSlider::handle:horizontal { background: #ffffff; width: 18px; height: 18px;
    margin: -7px 0; border-radius: 9px; border: 2px solid rgba(255,255,255,0.40); }
QSlider::handle:horizontal:hover { background: #f1f4ff;
    border: 2px solid rgba(255,255,255,0.65); }
QSlider::sub-page:horizontal:disabled { background: rgba(255,255,255,0.20); }
QSlider::handle:horizontal:disabled { background: rgba(255,255,255,0.45);
    border-color: rgba(255,255,255,0.15); }

QPlainTextEdit { background: rgba(4,6,12,0.55); color: #d9dcea;
    border: 1px solid rgba(255,255,255,0.09); border-radius: 14px; padding: 10px;
    selection-background-color: @A@; selection-color: @INK@; }


QLabel#progress { font-size: 15px; font-weight: 600; color: #ffffff; }
QLabel#statNum { font-size: 38px; font-weight: 700; color: #ffffff; }
QLabel#banner { background: rgba(255,255,255,0.10); border: 1px solid rgba(255,255,255,0.18);
    border-radius: 12px; padding: 10px 14px; font-weight: 600; }
QLabel#banner[tone="error"] { background: rgba(255,120,120,0.16); border-color: rgba(255,120,120,0.50);
    color: #ffb4ae; }
QLabel#banner[tone="ok"] { background: rgba(134,239,172,0.12); border-color: rgba(134,239,172,0.40);
    color: #a7f3c4; }
QLabel#error { color: rgba(252,165,165,0.96); }
QLabel#viewerMsg { font-size: 22px; font-weight: 600; color: rgba(238,240,248,0.55); }
QFrame#Viewer { background: rgba(4,6,12,0.55); border: 1px solid rgba(255,255,255,0.10);
    border-radius: 18px; }
QKeySequenceEdit { background: rgba(255,255,255,0.065); border: 1px solid rgba(255,255,255,0.13);
    border-radius: 11px; padding: 8px 13px; }
QKeySequenceEdit:focus { border: 1px solid @A_LINE@; background: rgba(255,255,255,0.10); }
QListWidget { background: rgba(255,255,255,0.05); border: 1px solid rgba(255,255,255,0.10);
    border-radius: 14px; padding: 6px; outline: 0; }
QListWidget::item { padding: 10px; border-radius: 9px; }
QListWidget::item:selected { background: @A_SOFT@; color: #ffffff; }

QScrollArea { background: transparent; border: none; }
QScrollArea > QWidget > QWidget { background: transparent; }
QScrollBar:vertical { background: transparent; width: 12px; margin: 4px 2px; }
QScrollBar::handle:vertical { background: rgba(255,255,255,0.16);
    border-radius: 4px; min-height: 36px; margin: 0 2px; }
QScrollBar::handle:vertical:hover { background: rgba(255,255,255,0.30); }
QScrollBar:horizontal { background: transparent; height: 12px; margin: 2px 4px; }
QScrollBar::handle:horizontal { background: rgba(255,255,255,0.16);
    border-radius: 4px; min-width: 36px; margin: 2px 0; }
QScrollBar::handle:horizontal:hover { background: rgba(255,255,255,0.30); }
QScrollBar::add-line, QScrollBar::sub-line { width: 0; height: 0; }
QScrollBar::add-page, QScrollBar::sub-page { background: transparent; }

QMessageBox, QDialog { background: @POP@; }
QMessageBox QLabel { color: @TEXT@; font-size: 13px; }
QDialog QPushButton, QMessageBox QPushButton { background: rgba(255,255,255,0.08);
    border: 1px solid rgba(255,255,255,0.16); border-radius: 10px;
    padding: 8px 20px; min-width: 72px; color: @TEXT@; }
QDialog QPushButton:hover, QMessageBox QPushButton:hover {
    background: rgba(255,255,255,0.14); border-color: @A_LINE@; }
QDialog QPushButton:default, QMessageBox QPushButton:default {
    background: @A@; color: @INK@; border: none; }
"""


def build_qss() -> str:
    p = current()
    f = QColor(p.fg)
    out = re.sub(r"rgba\(\s*238\s*,\s*240\s*,\s*248\s*,", "rgba(%d,%d,%d," % (f.red(), f.green(), f.blue()), _QSS)
    out = re.sub(r"rgba\(\s*255\s*,\s*255\s*,\s*255\s*,", "rgba(%s," % _ov_rgb(), out)
    return (out.replace("@TEXT@", p.fg)
            .replace("#ffffff", p.strong)
            .replace("@A_SOFT@", rgba(p.accent_a, 0.28))
            .replace("@A_LINE@", rgba(p.accent_a, 0.85))
            .replace("@POP@", popup_color())
            .replace("@INK@", p.ink)
            .replace("@A@", p.accent_a)
            .replace("@B@", p.accent_b))


def set_tone(widget, tone: str) -> None:
    """Change la propriété `tone` d'un QLabel et réapplique son style."""
    widget.setProperty("tone", tone)
    widget.style().unpolish(widget)
    widget.style().polish(widget)


def apply(app) -> None:
    """Applique style Fusion, police, palette Qt et feuille de style."""
    if app.style().objectName().lower() != "fusion":
        app.setStyle("Fusion")
    app.setFont(ui_font(10))

    p = current()
    pal = QPalette()
    R = QPalette.ColorRole
    roles = {
        R.Window: QColor(p.bg_top),
        R.WindowText: fg(),
        R.Base: QColor(p.surface),
        R.AlternateBase: QColor(p.card),
        R.Text: fg(),
        R.Button: QColor(p.card),
        R.ButtonText: fg(),
        R.Highlight: QColor(p.accent_a),
        R.HighlightedText: QColor(p.ink),
        R.ToolTipBase: QColor(popup_color()),
        R.ToolTipText: fg(),
        R.PlaceholderText: fg(105),
    }
    for role, color in roles.items():
        pal.setColor(role, color)
    for role in (R.Text, R.ButtonText, R.WindowText):
        pal.setColor(QPalette.ColorGroup.Disabled, role, fg(80))
    app.setPalette(pal)
    app.setStyleSheet(build_qss())
