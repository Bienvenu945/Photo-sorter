"""Bibliothèque : grille / liste, filtres, tri, multi-sélection (le tri par lot est géré par la fenêtre)."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject, QRunnable, Qt, QThreadPool, QTimer, Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget

from services.thumbnail_cache import THUMB_SIZES, ThumbnailCache
from widgets.controls import GlassButton, Segmented
from widgets.filter_bar import FilterBar
from widgets.glass import GlassCard
from widgets.grid_view import GridView, natural_key


class _SortSignals(QObject):
    done = Signal(int, object)


class _SortTask(QRunnable):
    def __init__(self, gen: int, photos: list[Path], key: str, signals: _SortSignals) -> None:
        super().__init__()
        self.gen, self.photos, self.key, self.signals = gen, photos, key, signals

    def run(self) -> None:
        def stat(p: Path):
            try:
                return p.stat()
            except OSError:
                return None
        try:
            if self.key == "size":
                out = sorted(self.photos, key=lambda p: -(stat(p).st_size if stat(p) else 0))
            else:  # date de modification, plus récentes d'abord
                out = sorted(self.photos, key=lambda p: -(stat(p).st_mtime_ns if stat(p) else 0))
        except Exception:
            out = list(self.photos)
        self.signals.done.emit(self.gen, out)


class LibraryPage(QWidget):
    openRequested = Signal(object)       # Path (double-clic)
    selectionChanged = Signal(object)    # list[Path]
    settingChanged = Signal(str, object)
    dateSortRequested = Signal()
    renameRequested = Signal()

    def __init__(self, cache: ThumbnailCache, settings: dict) -> None:
        super().__init__()
        self._all: list[Path] = []
        self._sorted: list[Path] = []
        self._query = ""
        self._shown = 0
        self._gen = 0
        self._sort_signals = _SortSignals()
        self._sort_signals.done.connect(self._on_sorted)

        px = settings.get("thumb_size", 192)
        self.grid = GridView(cache, px if px in THUMB_SIZES else 192, int(settings.get("grid_columns", 4)))
        self.grid.openRequested.connect(self.openRequested)
        self.grid.selectedPaths.connect(self._on_selection)

        title = QLabel("Bibliothèque")
        title.setObjectName("pageTitle")
        self.count = QLabel("")
        self.count.setObjectName("pageSub")
        self.filter_bar = FilterBar(settings.get("recent_filters", []))

        self.sort_ctl = Segmented([("Nom", "name"), ("Date", "date"), ("Taille", "size")])
        self.view_ctl = Segmented([("Grille", "grid"), ("Liste", "list")])
        self.cols_ctl = Segmented([("Auto", 0), ("3", 3), ("4", 4), ("5", 5), ("6", 6)])
        self.size_ctl = Segmented([("S", 128), ("M", 192), ("L", 256), ("XL", 384)])
        self.sort_ctl.set_value(settings.get("sort_by", "name"))
        self.view_ctl.set_value(settings.get("view_mode", "grid"))
        self.cols_ctl.set_value(self.grid.columns)
        self.size_ctl.set_value(self.grid.photo_model._px)
        self.sort_ctl.changed.connect(lambda v: (self.settingChanged.emit("sort_by", v), self._resort()))
        self.view_ctl.changed.connect(lambda v: (self.settingChanged.emit("view_mode", v), self.grid.set_mode(v)))
        self.cols_ctl.changed.connect(lambda v: (self.settingChanged.emit("grid_columns", v), self.set_columns(v)))
        self.size_ctl.changed.connect(lambda v: (self.settingChanged.emit("thumb_size", v), self.grid.set_thumb_px(v)))
        self.size_ctl.setEnabled(self.grid.columns == 0)

        self.banner = QLabel("")
        self.banner.setObjectName("banner")
        self.banner.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.banner.hide()
        self._banner_timer = QTimer(self, singleShot=True, interval=3500)
        self._banner_timer.timeout.connect(self.banner.hide)

        self.empty = QLabel("Aucune photo. Choisissez un dossier depuis l'accueil.")
        self.empty.setObjectName("viewerMsg")
        self.empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.card = GlassCard()
        self.card.layout().setContentsMargins(10, 10, 10, 10)
        self.card.add_widget(self.empty)
        self.card.add_widget(self.grid, 1)
        self.selection_label = QLabel("")
        self.selection_label.setObjectName("progress")
        self.footer = QLabel("")
        self.footer.setObjectName("hint")

        controls = QHBoxLayout()
        controls.setSpacing(14)
        for w in (self.sort_ctl, self.view_ctl, self.cols_ctl, self.size_ctl):
            controls.addWidget(w)
        controls.addStretch(1)
        b_date = GlassButton("Trier par date", "default", "grid")
        b_date.setToolTip("Ranger les photos dans des dossiers par date (Ctrl+R)")
        b_date.clicked.connect(self.dateSortRequested)
        b_ren = GlassButton("Renommer en lot", "default", "edit")
        b_ren.setToolTip("Renommer selon un modèle (Ctrl+B)")
        b_ren.clicked.connect(self.renameRequested)
        controls.addWidget(b_date)
        controls.addWidget(b_ren)
        bottom = QHBoxLayout()
        bottom.addWidget(self.selection_label)
        bottom.addStretch(1)
        bottom.addWidget(self.footer)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(2, 2, 14, 10)
        lay.setSpacing(10)
        lay.addWidget(title)
        lay.addWidget(self.count)
        lay.addWidget(self.filter_bar)
        lay.addLayout(controls)
        lay.addWidget(self.banner)
        lay.addWidget(self.card, 1)
        lay.addLayout(bottom)
        self.grid.set_mode(settings.get("view_mode", "grid"))
        self._update_labels()

    # ----- API -----
    def set_photos(self, photos: list[Path]) -> None:
        self._all = list(photos)
        self._resort()

    def set_search(self, text: str) -> None:
        self._query = text.strip().lower()
        self._apply()

    def set_columns(self, columns: int) -> None:
        self.grid.set_columns(columns)
        self.size_ctl.setEnabled(columns == 0)

    def selected(self) -> list[Path]:
        return self.grid.selected()

    def current_path(self) -> Path | None:
        return self.grid.current_path()

    def select_all(self) -> None:
        self.grid.selectAll()

    def clear_selection(self) -> bool:
        """Désélectionne tout ; retourne False s'il n'y avait aucune sélection."""
        had = bool(self.grid.selected())
        self.grid.clearSelection()
        return had

    def flash(self, text: str, tone: str = "ok") -> None:
        """Confirmation visuelle (« 15 photos triées vers Famille »)."""
        import theme
        self.banner.setText(text)
        theme.set_tone(self.banner, tone)
        self.banner.show()
        self._banner_timer.start()

    # ----- interne -----
    def _on_selection(self, paths: list) -> None:
        n = len(paths)
        self.selection_label.setText(f"{n} sélectionnée{'s' if n > 1 else ''}" if n else "")
        self.selectionChanged.emit(paths)

    def _resort(self) -> None:
        self._gen += 1
        key = self.sort_ctl.value()
        if key == "name":
            self._sorted = sorted(self._all, key=natural_key)  # pas d'I/O : immédiat
            self._apply()
        else:
            QThreadPool.globalInstance().start(_SortTask(self._gen, list(self._all), key, self._sort_signals))

    def _on_sorted(self, gen: int, photos: list[Path]) -> None:
        if gen == self._gen:
            self._sorted = photos
            self._apply()

    def _apply(self) -> None:
        shown = [p for p in self._sorted if self._query in p.name.lower()] if self._query else self._sorted
        self.grid.set_photos(shown)
        self._shown = len(shown)
        self._update_labels()
        self._on_selection([])

    def _update_labels(self) -> None:
        total = len(self._all)
        self.empty.setVisible(self._shown == 0)
        self.grid.setVisible(self._shown > 0)
        if self._query:
            self.count.setText(f"{self._shown} résultat(s) sur {total} photo(s)")
            self.empty.setText("Aucun résultat pour cette recherche.")
        else:
            self.count.setText(f"{total} photo(s) dans la file" if total else "")
            self.empty.setText("Aucune photo. Choisissez un dossier depuis l'accueil." if not total
                               else "Aucune photo dans la file (filtre actif ?).")
        self.footer.setText("Double-clic : ouvrir  ·  Ctrl / Maj + clic : sélection  ·  Ctrl+A : tout  ·  "
                            "1-9 : trier la sélection")
