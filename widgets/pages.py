"""Pages de l'application : Dossiers, Catégories, Statistiques, Réglages, Trier."""
from __future__ import annotations

import html
from pathlib import Path

from PySide6.QtCore import QRectF, Qt, Signal
from PySide6.QtGui import QColor, QFontMetrics, QLinearGradient, QBrush, QPainter
from PySide6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget

import theme
from config import ConfigManager
from widgets.base_page import BasePage
from widgets.category_bar import CategoryBar
from widgets.controls import GlassButton, GlassCombo, Segmented, Toggle, hbox
from widgets.glass import GlassCard, SettingRow
from widgets.navigation_bar import NavigationBar
from widgets.viewer import Viewer


def _bind(cfg: ConfigManager, ctrl, key: str, emit) -> None:
    ctrl.set_value(cfg.settings.get(key))
    ctrl.changed.connect(lambda v, k=key: emit(k, v))


# ----------------------------------------------------------------------
class CategoriesPage(BasePage):
    TITLE = "Catégories"
    SUBTITLE = "Entièrement personnalisables : aucune n'est imposée. Un profil = un jeu de catégories."
    manage_categories = Signal()
    profile_chosen = Signal(str)

    def build(self) -> None:
        self.profile_card = self.card("Profils")
        self.chips_box = QWidget()
        self.chips_lay = QHBoxLayout(self.chips_box)
        self.chips_lay.setContentsMargins(0, 4, 0, 14)
        self.chips_lay.setSpacing(8)
        self.profile_card.add_widget(self.chips_box)
        self.list_card = self.card("Vos catégories")
        self.list_body = QVBoxLayout()
        self.list_card.add_widget(self._wrap(self.list_body))
        btn = GlassButton("Gérer les catégories", "primary", "edit")
        btn.clicked.connect(self.manage_categories)
        self._v.addWidget(btn, 0, Qt.AlignmentFlag.AlignLeft)

    @staticmethod
    def _wrap(layout) -> QWidget:
        w = QWidget()
        layout.setContentsMargins(0, 0, 0, 0)
        w.setLayout(layout)
        return w

    def on_enter(self) -> None:
        self.refresh()

    def refresh(self) -> None:
        for lay in (self.chips_lay, self.list_body):
            while lay.count():
                it = lay.takeAt(0)
                if it.widget():
                    it.widget().deleteLater()
        for name in self.cfg.profile_names():
            chip = GlassButton(name, "chip")
            chip.set_active(name == self.cfg.active_profile)
            chip.clicked.connect(lambda _=False, n=name: self.profile_chosen.emit(n))
            self.chips_lay.addWidget(chip)
        self.chips_lay.addStretch(1)
        cats = self.cfg.categories()
        if not cats:
            hint = QLabel("Aucune catégorie pour l'instant. Créez-en pour commencer à trier.")
            hint.setObjectName("hint")
            hint.setContentsMargins(0, 8, 0, 16)
            self.list_body.addWidget(hint)
        for i, c in enumerate(cats):
            pill = QLabel(c.shortcut or "?")
            pill.setObjectName("pill")
            row = SettingRow("", pill)
            row._title.setText(f'<span style="color:{c.color}">●</span>&nbsp;&nbsp;{html.escape(c.name)}')
            self.list_body.addWidget(row)


# ----------------------------------------------------------------------
class _Tile(QWidget):
    def __init__(self, caption: str) -> None:
        super().__init__()
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 4, 0, 14)
        lay.setSpacing(0)
        self.num = QLabel("0")
        self.num.setObjectName("statNum")
        cap = QLabel(caption)
        cap.setObjectName("muted")
        lay.addWidget(self.num)
        lay.addWidget(cap)


class BarList(QWidget):
    ROW = 36

    def __init__(self) -> None:
        super().__init__()
        self._rows: list[tuple[str, int, str]] = []
        self.setMinimumHeight(self.ROW)

    def set_rows(self, rows: list[tuple[str, int, str]]) -> None:
        self._rows = rows
        self.setMinimumHeight(max(1, len(rows)) * self.ROW + 10)
        self.update()

    def paintEvent(self, _e) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        top = max([n for _, n, _ in self._rows] + [1])
        font = theme.ui_font(10)
        p.setFont(font)
        fm = QFontMetrics(font)
        left, right = 170, 54
        for i, (name, n, color) in enumerate(self._rows):
            y = i * self.ROW + 5
            p.setPen(theme.fg(230))
            p.drawText(QRectF(0, y, left - 12, 24), Qt.AlignmentFlag.AlignVCenter,
                       fm.elidedText(name, Qt.TextElideMode.ElideRight, left - 12))
            track = QRectF(left, y + 7, max(10, self.width() - left - right), 10)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(theme.ov(22))
            p.drawRoundedRect(track, 5, 5)
            if n:
                fill = QRectF(track.left(), track.top(), max(10.0, track.width() * n / top), 10)
                g = QLinearGradient(fill.left(), 0, fill.right(), 0)
                g.setColorAt(0, theme.qcolor(color, 0.55))
                g.setColorAt(1, QColor(color))
                p.setBrush(QBrush(g))
                p.drawRoundedRect(fill, 5, 5)
            p.setPen(theme.fg(200))
            p.drawText(QRectF(self.width() - right + 8, y, right - 8, 24),
                       Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight, str(n))


# ----------------------------------------------------------------------
class SettingsPage(BasePage):
    TITLE = "Réglages"
    SUBTITLE = "Comportement du tri, apparence et panneaux."
    setting_changed = Signal(str, object)

    def build(self) -> None:
        c = self.cfg
        emit = self.setting_changed.emit
        card = self.card("Tri")
        mode = Segmented([("Déplacer", "move"), ("Copier", "copy")])
        _bind(c, mode, "mode", emit)
        self.row(card, "Mode", mode, "Déplacer retire la photo du dossier source ; Copier la conserve.")
        pol = Segmented([("Renommer", "rename"), ("Ignorer", "skip"), ("Remplacer", "replace")])
        _bind(c, pol, "duplicate_policy", emit)
        self.row(card, "Doublons", pol, "« Remplacer » écrase le fichier existant : à utiliser avec prudence.")
        sub = Toggle()
        _bind(c, sub, "include_subdirs", emit)
        self.row(card, "Inclure les sous-dossiers", sub,
                 "Les dossiers portant le nom d'une catégorie sont toujours ignorés.")

        look = self.card("Apparence")
        pal = GlassCombo(theme.PALETTE_CHOICES, width=240)
        _bind(c, pal, "palette", emit)
        self.row(look, "Thème", pal, "HyperOS sombre (référence), clair, hacker, ou palettes « verre ».")
        b_pick = GlassButton("Choisir…", "default")
        b_reset = GlassButton("Par défaut", "ghost")
        b_pick.clicked.connect(self._pick_accent)
        b_reset.clicked.connect(lambda: emit("accent", None))
        self.row(look, "Couleur d'accent", hbox(b_pick, b_reset), "Remplace l'accent du thème choisi.")
        cols = Segmented([("Auto", 0), ("3", 3), ("4", 4), ("5", 5), ("6", 6)])
        _bind(c, cols, "grid_columns", emit)
        self.row(look, "Colonnes de la grille", cols, "4 par défaut ; « Auto » utilise la taille des miniatures.")
        size = Segmented([("128", 128), ("192", 192), ("256", 256), ("384", 384)])
        _bind(c, size, "thumb_size", emit)
        self.row(look, "Taille des miniatures", size, "Pixels (mode colonnes « Auto »).")

        grid = self.card("Grille et tri par lot")
        gkey = Toggle()
        _bind(c, gkey, "grid_shortcut", emit)
        self.row(grid, "Touche G (grille ⇄ tri)", gkey, "Désactivez pour ne garder que l'espace de tri.")
        batch = Toggle()
        _bind(c, batch, "batch_sort", emit)
        self.row(grid, "Tri par lot depuis la grille", batch, "Une touche de catégorie trie toute la sélection (un seul Ctrl+Z).")
        limit = GlassCombo([("25 photos", 25), ("50 photos", 50), ("100 photos", 100), ("250 photos", 250),
                            ("500 photos", 500)], width=200)
        _bind(c, limit, "batch_limit", emit)
        self.row(grid, "Limite par tri groupé", limit, "Un avertissement s'affiche au-delà.")
        cache = GlassCombo([("250 Mo", 250), ("500 Mo", 500), ("1 Go", 1024), ("2 Go", 2048)], width=200)
        _bind(c, cache, "cache_max_mb", emit)
        self.row(grid, "Taille max du cache de miniatures", cache, "Les plus anciennes sont supprimées au-delà.")
        b_cache = GlassButton("Vider le cache", "default")
        b_cache.clicked.connect(lambda: emit("clear_cache", True))
        self.row(grid, "Miniatures en cache", b_cache, "Elles seront régénérées à la demande.")

        tools = self.card("Outils")
        dsort = Toggle()
        _bind(c, dsort, "date_sort", emit)
        self.row(tools, "Tri par date (Ctrl+R)", dsort, "Aperçu obligatoire avant tout déplacement.")
        ren = Toggle()
        _bind(c, ren, "batch_rename", emit)
        self.row(tools, "Renommer en lot (Ctrl+B)", ren, "Modèle avec variables ; annulable avec Ctrl+Z.")

        panels = self.card("Panneaux et effets")
        info = Toggle()
        _bind(c, info, "info_panel", emit)
        self.row(panels, "Panneau d'informations", info, "Métadonnées de la photo (touche F11 : mode focus).")
        anim = Toggle()
        _bind(c, anim, "animations", emit)
        self.row(panels, "Animations d'interface", anim, "Transitions entre les vues. À désactiver sur une machine lente.")
        bg = Toggle()
        _bind(c, bg, "animated", emit)
        self.row(panels, "Fond animé", bg, "Uniquement pour les palettes « verre » (Aurore, Or, Océan).")

    def _pick_accent(self) -> None:
        from PySide6.QtGui import QColor
        from PySide6.QtWidgets import QColorDialog

        col = QColorDialog.getColor(QColor(theme.current().accent_a), self, "Couleur d'accent")
        if col.isValid():
            self.setting_changed.emit("accent", col.name())


# ----------------------------------------------------------------------
class SortPage(QWidget):
    """Visionneuse + catégories + navigation."""

    def __init__(self) -> None:
        super().__init__()
        lay = QVBoxLayout(self)
        lay.setContentsMargins(2, 2, 14, 10)
        lay.setSpacing(14)
        self.banner = QLabel("")
        self.banner.setObjectName("banner")
        self.banner.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.banner.hide()
        self.filter_chip = QLabel("")
        self.filter_chip.setObjectName("banner")
        self.filter_chip.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.filter_chip.hide()
        self.viewer = Viewer()
        vcard = GlassCard()
        vcard.layout().setContentsMargins(12, 12, 12, 12)
        vcard.add_widget(self.viewer, 1)
        self.catbar = CategoryBar()
        self.nav = NavigationBar()
        bottom = GlassCard()
        bottom.layout().setContentsMargins(20, 18, 20, 16)
        bottom.layout().setSpacing(14)
        bottom.add_widget(self.catbar)
        bottom.add_widget(self.nav)
        lay.addWidget(self.banner)
        lay.addWidget(self.filter_chip)
        lay.addWidget(vcard, 1)
        lay.addWidget(bottom)

    def set_categories(self, cats) -> None:
        self.catbar.set_categories(cats)

    def set_filter_chip(self, text: str) -> None:
        """Indicateur visuel : un filtre réduit la file de tri."""
        self.filter_chip.setText(text)
        self.filter_chip.setVisible(bool(text))
