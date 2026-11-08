"""Tableau de bord : démarrer une session, dossiers récents, activité."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget

from widgets.base_page import BasePage
from widgets.controls import GlassButton, hbox
from widgets.pages import BarList, _Tile


class DashboardPage(BasePage):
    TITLE = "Accueil"
    SUBTITLE = "Choisissez un dossier, ouvrez la bibliothèque ou lancez directement le tri."
    choose_source = Signal()
    choose_dest = Signal()
    open_library = Signal()
    start = Signal()
    manage_categories = Signal()
    open_settings = Signal()
    open_history = Signal()
    recent_chosen = Signal(str)

    def build(self) -> None:
        card = self.card("Nouvelle session")
        b_src = GlassButton("Choisir…", "default", "folder")
        b_dst = GlassButton("Choisir…", "default", "folder")
        b_src.clicked.connect(self.choose_source)
        b_dst.clicked.connect(self.choose_dest)
        self.src_row = self.row(card, "Dossier source", b_src, "Aucun dossier choisi")
        self.dst_row = self.row(card, "Dossier destination (recommandé)", b_dst,
                                "Identique à la source — les dossiers de catégories y seront créés")
        b_lib = GlassButton("Ouvrir la bibliothèque", "default", "grid")
        b_go = GlassButton("Commencer le tri", "primary", "play")
        b_lib.clicked.connect(self.open_library)
        b_go.clicked.connect(self.start)
        self.info_row = self.row(card, "Profil et catégories", hbox(b_lib, b_go), "")

        self.recent_card = self.card("Dossiers récents")
        self.recent_box = QWidget()
        self.recent_lay = QHBoxLayout(self.recent_box)
        self.recent_lay.setContentsMargins(0, 4, 0, 14)
        self.recent_lay.setSpacing(8)
        self.recent_card.add_widget(self.recent_box)

        act = self.card("Activité de la session")
        self.t_done, self.t_left, self.t_cats = _Tile("Traitées"), _Tile("Restantes"), _Tile("Catégories")
        act.add_widget(hbox(self.t_done, self.t_left, self.t_cats, spacing=40))
        self.bars = BarList()
        act.add_widget(self.bars)

        self.sessions_card = self.card("Dernières sessions")
        self.sessions_lay = QVBoxLayout()
        self.sessions_lay.setContentsMargins(0, 0, 0, 12)
        wrap = QWidget()
        wrap.setLayout(self.sessions_lay)
        self.sessions_card.add_widget(wrap)

        quick = self.card("Raccourcis")
        b_cat = GlassButton("Gérer les catégories", "default", "tag")
        b_set = GlassButton("Réglages", "default", "sliders")
        b_his = GlassButton("Historique", "default", "undo")
        b_cat.clicked.connect(self.manage_categories)
        b_set.clicked.connect(self.open_settings)
        b_his.clicked.connect(self.open_history)
        quick.add_widget(hbox(b_cat, b_his, b_set))

    # ----- mises à jour -----
    def set_paths(self, src: Path | None, dst: Path | None) -> None:
        self.src_row.set_hint(str(src) if src else "Aucun dossier choisi", "ok" if src else "")
        self.dst_row.set_hint(str(dst) if dst else "Identique à la source — les dossiers de catégories y seront créés",
                              "ok" if dst else "")

    def set_info(self, text: str) -> None:
        self.info_row.set_hint(text)

    @staticmethod
    def _clear(layout) -> None:
        while layout.count():
            item = layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def set_recent(self, folders: list[str]) -> None:
        self._clear(self.recent_lay)
        if not folders:
            hint = QLabel("Aucun dossier récent.")
            hint.setObjectName("hint")
            self.recent_lay.addWidget(hint)
        for f in folders[:6]:
            chip = GlassButton(Path(f).name or f, "chip")
            chip.setToolTip(f)
            chip.clicked.connect(lambda _=False, folder=f: self.recent_chosen.emit(folder))
            self.recent_lay.addWidget(chip)
        self.recent_lay.addStretch(1)

    def set_stats(self, stats: dict, categories) -> None:
        self.t_done.num.setText(str(stats["processed"]))
        self.t_left.num.setText(str(stats["remaining"]))
        self.t_cats.num.setText(str(len(categories)))
        self.bars.set_rows([(c.name, stats["counts"].get(c.id, 0), c.color) for c in categories])

    def set_sessions(self, sessions: list[dict]) -> None:
        self._clear(self.sessions_lay)
        if not sessions:
            hint = QLabel("Aucune session enregistrée.")
            hint.setObjectName("hint")
            self.sessions_lay.addWidget(hint)
        for s in sessions[:4]:
            line = QLabel(f"{s.get('date', '')}  ·  {Path(s.get('folder', '')).name}  ·  "
                          f"{s.get('processed', 0)} photo(s) triée(s)")
            line.setContentsMargins(0, 4, 0, 4)
            self.sessions_lay.addWidget(line)
