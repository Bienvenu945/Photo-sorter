"""Fenêtre principale — 5 zones : A barre supérieure, B navigation, C zone principale, D infos, E statut."""
from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QEvent, Qt, QTimer
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (QApplication, QFileDialog, QHBoxLayout, QMainWindow, QMessageBox, QSizeGrip,
                               QVBoxLayout, QWidget)

import theme
from config import APP_TITLE, AUTHOR, VERSION, YEAR, ConfigManager
from models import PhotoSorterModel
from services import file_manager as fm
from services.batch_ops import execute_plan
from services.history_db import HistoryDB, redo_last, undo_last
from services.thumbnail_cache import ThumbnailCache
from views.dashboard import DashboardPage
from views.library import LibraryPage
from widgets import icons
from widgets.batch_rename_dialog import BatchRenameDialog
from widgets.category_manager import CategoryManager
from widgets.date_sorter_dialog import DateSorterDialog
from widgets.glass import AuroraBackground, FadeStack
from widgets.history_dialog import HistoryDialog
from widgets.info_panel import InfoPanel
from widgets.pages import CategoriesPage, SettingsPage, SortPage
from widgets.sidebar import Sidebar
from widgets.status_bar import StatusBar
from widgets.titlebar import TitleBar

logger = logging.getLogger(__name__)

CORNER_RADIUS = 24.0
NAV = [("home", "Accueil"), ("grid", "Bibliothèque"), ("image", "Trier"), ("tag", "Catégories"),
       ("sliders", "Réglages")]
IDX_HOME, IDX_LIB, IDX_SORT, IDX_CATS, IDX_SETTINGS = range(5)
HINTS = {IDX_HOME: "Ctrl+,  réglages  ·  Ctrl+H  historique",
         IDX_LIB: "1-9  trier la sélection  ·  Ctrl+R  par date  ·  Ctrl+B  renommer  ·  G  tri  ·  Ctrl+H  historique",
         IDX_SORT: "touches  trier  ·  ← →  naviguer  ·  Ctrl+Z / Ctrl+Maj+Z  annuler / rétablir  ·  G  grille",
         IDX_CATS: "", IDX_SETTINGS: ""}


class MainWindow(QMainWindow):
    def __init__(self, cfg: ConfigManager, native_frame: bool = False, history: HistoryDB | None = None) -> None:
        super().__init__()
        self.cfg, self.model = cfg, PhotoSorterModel()
        self.history = history or HistoryDB()
        self.thumbs = ThumbnailCache(max_bytes=int(cfg.settings.get("cache_max_mb", 500)) * 1024 * 1024)
        self.native = native_frame or bool(cfg.settings.get("native_titlebar"))
        self.src_dir = self._saved_dir("last_source_dir")
        self.dst_dir = self._saved_dir("last_dest_dir")
        self.focus_mode = False
        self._session_saved = 0
        self.setWindowTitle(f"{APP_TITLE} — {AUTHOR}")
        self.resize(1280, 840)
        self.setMinimumSize(1060, 720)
        if not self.native:
            self.setWindowFlag(Qt.WindowType.FramelessWindowHint, True)
            self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self._build_ui()
        self._wire()
        self.shell.set_radius(0 if self.native else CORNER_RADIUS)
        self.shell.set_animated(bool(cfg.settings.get("animated", True)))
        self.stack.animate = bool(cfg.settings.get("animations", True))
        self.dashboard.set_paths(self.src_dir, self.dst_dir)
        self._rebuild_shortcuts()
        self._update_info()
        self._refresh_dashboard()
        self._update_panels()
        self._update_status()

    # ------------------------------------------------------------------ UI
    def _build_ui(self) -> None:
        self.shell = AuroraBackground()
        self.setCentralWidget(self.shell)
        outer = QVBoxLayout(self.shell)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        self.titlebar = TitleBar(self.native)                       # A
        outer.addWidget(self.titlebar)
        body = QHBoxLayout()
        body.setContentsMargins(20, 0, 20, 6)
        body.setSpacing(18)
        outer.addLayout(body, 1)
        self.sidebar = Sidebar(NAV)                                 # B
        body.addWidget(self.sidebar)

        self.stack = FadeStack()                                    # C
        self.dashboard = DashboardPage()
        self.library = LibraryPage(self.thumbs, self.cfg.settings)
        self.sort_page = SortPage()
        self.cats_page = CategoriesPage(self.cfg)
        self.settings_page = SettingsPage(self.cfg)
        for page in (self.dashboard, self.library, self.sort_page, self.cats_page, self.settings_page):
            self.stack.addWidget(page)
        body.addWidget(self.stack, 1)
        self.info = InfoPanel()                                     # D
        body.addWidget(self.info)

        self.status = StatusBar()                                   # E
        wrap = QWidget()
        wl = QHBoxLayout(wrap)
        wl.setContentsMargins(26, 0, 26, 12)
        wl.addWidget(self.status)
        outer.addWidget(wrap)
        self._status_wrap = wrap

        self._grip = None
        self._banner_timer = QTimer(self, singleShot=True, interval=4500)
        self._banner_timer.timeout.connect(self.sort_page.banner.hide)
        if not self.native:
            self._grip = QSizeGrip(self.shell)
            self._grip.setFixedSize(18, 18)
            self._grip.raise_()

    def _wire(self) -> None:
        d, sp = self.dashboard, self.sort_page
        self.sidebar.currentChanged.connect(self._on_page)
        self.sidebar.aboutRequested.connect(self.show_about)
        self.titlebar.searchChanged.connect(self._on_search)
        self.titlebar.settingsRequested.connect(lambda: self.sidebar.set_current(IDX_SETTINGS))
        d.choose_source.connect(self._pick_source)
        d.choose_dest.connect(self._pick_dest)
        d.manage_categories.connect(self._manage)
        d.open_settings.connect(lambda: self.sidebar.set_current(IDX_SETTINGS))
        d.open_library.connect(lambda: self._open_session(IDX_LIB))
        d.start.connect(lambda: self._open_session(IDX_SORT))
        d.recent_chosen.connect(self._use_recent)
        self.library.openRequested.connect(self._open_from_library)
        self.library.selectionChanged.connect(self._on_library_selection)
        self.library.settingChanged.connect(lambda k, v: self.cfg.set(k, v))
        self.library.filter_bar.filterApplied.connect(self._on_filter)
        self.library.dateSortRequested.connect(self.show_date_sorter)
        self.library.renameRequested.connect(self.show_batch_rename)
        self.library.filter_bar.recentChanged.connect(lambda r: self.cfg.set("recent_filters", r))
        d.open_history.connect(self.show_history)
        self.cats_page.manage_categories.connect(self._manage)
        self.cats_page.profile_chosen.connect(self._switch_profile)
        self.settings_page.setting_changed.connect(self._setting_changed)
        sp.catbar.category_chosen.connect(self.sort_to)
        sp.nav.previous.connect(self._previous)
        sp.nav.skip.connect(self._skip)
        sp.nav.undo.connect(self._undo)
        sp.viewer.load_failed.connect(lambda p, m: self.notify(f"{Path(p).name} : {m}", "error"))
        self._cat_shortcuts: list[QShortcut] = []
        for seq, fn in (("Left", self._previous), ("Right", self._skip), ("Space", self._skip),
                        ("Ctrl+Z", self._undo), ("Esc", self._escape), ("G", self._toggle_grid),
                        ("F11", self._toggle_focus), ("Ctrl+,", lambda: self.sidebar.set_current(IDX_SETTINGS)),
                        ("Ctrl+Shift+Z", self._redo), ("Ctrl+H", self.show_history), ("Ctrl+A", self._select_all),
                        ("Ctrl+R", self.show_date_sorter), ("Ctrl+B", self.show_batch_rename)):
            QShortcut(QKeySequence(seq), self).activated.connect(fn)

    def _saved_dir(self, key: str) -> Path | None:
        v = self.cfg.settings.get(key)
        return Path(v) if v and Path(v).is_dir() else None

    # ------------------------------------------------------------ navigation
    def _on_page(self, index: int) -> None:
        self.stack.set_index(index)
        if index == IDX_LIB:
            self.library.set_photos(self._remaining())
        elif index == IDX_CATS:
            self.cats_page.refresh()
        elif index == IDX_HOME:
            self._refresh_dashboard()
        elif index == IDX_SORT:
            self._show_current_info()
        self._update_panels()
        self._update_status()

    def _toggle_grid(self) -> None:
        if (QApplication.activeModalWidget() or not self.model.total
                or not self.cfg.settings.get("grid_shortcut", True)):
            return
        page = self.sidebar.current()
        if page == IDX_SORT:
            self.sidebar.set_current(IDX_LIB)
        elif page == IDX_LIB:
            self.sidebar.set_current(IDX_SORT)

    def _toggle_focus(self) -> None:
        self.focus_mode = not self.focus_mode
        self._update_panels()

    def _update_panels(self) -> None:
        page = self.sidebar.current()
        self.sidebar.setVisible(not self.focus_mode)
        self._status_wrap.setVisible(not self.focus_mode)
        wants_info = bool(self.cfg.settings.get("info_panel", True)) and page in (IDX_LIB, IDX_SORT)
        self.info.setVisible(wants_info and not self.focus_mode)

    def _escape(self) -> None:
        if QApplication.activeModalWidget():
            return
        if self.focus_mode:
            self._toggle_focus()
        elif self.sidebar.current() == IDX_LIB and self.library.clear_selection():
            return  # Échap : désélectionne d'abord
        elif self.sidebar.current() != IDX_HOME:
            self.sidebar.set_current(IDX_HOME)
        else:
            self.close()

    def _select_all(self) -> None:
        if self.sidebar.current() == IDX_LIB and not QApplication.activeModalWidget():
            self.library.select_all()

    def _on_search(self, text: str) -> None:
        self.library.set_search(text)
        if text and self.sidebar.current() != IDX_LIB and self.model.total:
            self.sidebar.set_current(IDX_LIB)

    # --------------------------------------------------------------- dossiers
    def _pick_source(self) -> None:
        d = QFileDialog.getExistingDirectory(self, "Dossier source", str(self.src_dir or Path.home()))
        if d:
            self._set_source(Path(d))

    def _set_source(self, folder: Path) -> None:
        self.src_dir = folder
        self.cfg.set("last_source_dir", str(folder))
        self.dashboard.set_paths(self.src_dir, self.dst_dir)

    def _use_recent(self, folder: str) -> None:
        if Path(folder).is_dir():
            self._set_source(Path(folder))
        else:
            self.notify("Ce dossier n'existe plus.", "error")

    def _pick_dest(self) -> None:
        d = QFileDialog.getExistingDirectory(self, "Dossier destination",
                                             str(self.dst_dir or self.src_dir or Path.home()))
        if d:
            self.dst_dir = Path(d)
            self.cfg.set("last_dest_dir", d)
            self.dashboard.set_paths(self.src_dir, self.dst_dir)

    def _manage(self) -> None:
        CategoryManager(self.cfg, self).exec()
        self._after_categories_changed()

    def _switch_profile(self, name: str) -> None:
        self.cfg.switch_profile(name)
        self._after_categories_changed()

    def _after_categories_changed(self) -> None:
        self._rebuild_shortcuts()
        self._update_info()
        self.cats_page.refresh()
        self._refresh_dashboard()
        if self.model.total:
            self.sort_page.set_categories(self.cfg.categories())

    def _update_info(self) -> None:
        n = len(self.cfg.categories())
        text = f"Profil « {self.cfg.active_profile} » · {n} catégorie{'s' if n > 1 else ''}"
        self.dashboard.set_info(text)
        self.titlebar.set_version(text)

    # ---------------------------------------------------------------- session
    def _remaining(self) -> list[Path]:
        m = self.model
        return [p for i, p in enumerate(m.photos) if i not in m.done and (m.allowed is None or i in m.allowed)]

    def _open_session(self, target: int) -> None:
        cats = self.cfg.categories()
        if not self.src_dir or not self.src_dir.is_dir():
            QMessageBox.warning(self, APP_TITLE, "Choisissez d'abord un dossier source valide.")
            return
        if target == IDX_SORT and not cats:
            QMessageBox.information(self, APP_TITLE, "Créez au moins une catégorie (« Gérer les catégories »).")
            return
        self._record_session()
        names = [fm.safe_folder_name(c.name) for c in cats]
        s = self.cfg.settings
        n = self.model.load_folder(self.src_dir, names if s.get("exclude_subdirs", True) else [],
                                   s.get("include_subdirs", False), [self.dst_dir] if self.dst_dir else [])
        if n == 0:
            QMessageBox.information(self, APP_TITLE, "Aucune photo compatible dans ce dossier.")
            return
        self._session_saved = 0
        recent = [str(self.src_dir)] + [f for f in s.get("recent_folders", []) if f != str(self.src_dir)]
        self.cfg.set("recent_folders", recent[:6])
        self.sort_page.set_categories(cats)
        self.library.filter_bar.set_session(list(self.model.photos))
        self.sort_page.set_filter_chip("")
        self.sidebar.set_current(target)
        if self.model.ignored:
            self.notify(f"{self.model.ignored} fichier(s) non compatible(s) ignoré(s).", "")
        self.refresh()

    def _open_from_library(self, path: Path) -> None:
        idx = self.model.index_of(Path(path))
        if idx is None or not self.model.go_to(idx):
            return
        if not self.cfg.categories():
            self.notify("Créez d'abord au moins une catégorie.", "error")
            return
        self.sort_page.set_categories(self.cfg.categories())
        self.sidebar.set_current(IDX_SORT)
        self.refresh()

    def _on_library_selection(self, paths: list) -> None:
        if self.sidebar.current() == IDX_LIB:
            self.info.show_photo(paths[0] if paths else None)
            self._update_status(len(paths))

    def _record_session(self) -> None:
        processed = self.model.stats()["processed"]
        if processed > self._session_saved and self.src_dir:
            sessions = self.cfg.settings.get("sessions", [])
            sessions.insert(0, {"date": datetime.now().strftime("%d/%m/%Y %H:%M"), "folder": str(self.src_dir),
                                "processed": processed})
            self.cfg.set("sessions", sessions[:10])
            self._session_saved = processed

    # ------------------------------------------------------------------- tri
    def _in_sort(self) -> bool:
        return self.sidebar.current() == IDX_SORT and QApplication.activeModalWidget() is None

    def _rebuild_shortcuts(self) -> None:
        for sc in self._cat_shortcuts:
            sc.setEnabled(False)
            sc.deleteLater()
        self._cat_shortcuts = []
        for c in self.cfg.categories():
            sc = QShortcut(QKeySequence(c.shortcut), self)
            sc.activated.connect(lambda cid=c.id: self.sort_to(cid))
            self._cat_shortcuts.append(sc)

    def sort_to(self, cat_id: str) -> None:
        """Trie la photo active (espace de tri) ou la sélection (grille) vers une catégorie."""
        if QApplication.activeModalWidget():
            return
        page = self.sidebar.current()
        if page == IDX_SORT:
            self._sort_single(cat_id)
        elif page == IDX_LIB and self.cfg.settings.get("batch_sort", True):
            self._sort_selection(cat_id)

    def _sort_single(self, cat_id: str) -> None:
        photo = self.model.current()
        if photo is None:
            return
        cat = self.cfg.category(cat_id)
        if cat is None:
            self.notify("Catégorie inexistante.", "error")
            return
        root = self.dst_dir or self.src_dir
        s = self.cfg.settings
        try:
            dst = fm.transfer(photo, root / fm.safe_folder_name(cat.name), s["mode"], s["duplicate_policy"])
        except fm.FileOperationError as e:
            logger.warning("Tri échoué: %s", e)
            if not photo.exists():
                self.model.discard_current()
                self.refresh()
            self.notify(str(e), "error")
            return
        if dst is None:
            self.notify("Doublon ignoré.", "")
            self.model.skip()
        else:
            self.history.record(photo, dst, cat.id, s["mode"])
            self.model.register(photo, dst, cat.id, s["mode"])
        self.refresh()

    def _sort_selection(self, cat_id: str) -> None:
        """Tri par lot : une seule opération de groupe dans l'historique (un seul Ctrl+Z)."""
        cat = self.cfg.category(cat_id)
        targets = self.library.selected()
        if not targets and self.library.current_path() is not None:
            targets = [self.library.current_path()]  # aucune sélection : photo active uniquement
        if cat is None or not targets:
            self.library.flash("Sélectionnez des photos, puis appuyez sur une touche de catégorie.", "")
            return
        limit = int(self.cfg.settings.get("batch_limit", 100))
        if len(targets) > limit:
            QMessageBox.warning(self, APP_TITLE, f"{len(targets)} photos sélectionnées : la limite par tri groupé est "
                                f"de {limit}.\nRéduisez la sélection ou augmentez la limite dans Réglages.")
            return
        root = self.dst_dir or self.src_dir
        s = self.cfg.settings
        folder = root / fm.safe_folder_name(cat.name)
        moved: list[tuple[Path, Path, str, str]] = []
        errors, skipped, last_error = 0, 0, ""
        for photo in targets:
            idx = self.model.index_of(photo)
            try:
                dst = fm.transfer(photo, folder, s["mode"], s["duplicate_policy"])
            except fm.FileOperationError as e:
                errors, last_error = errors + 1, str(e)
                logger.warning("Tri par lot : %s", e)
                continue
            if dst is None:
                skipped += 1
            elif idx is not None:
                self.model.register_at(idx, dst, cat.id, s["mode"])
                moved.append((photo, dst, cat.id, s["mode"]))
        if len(moved) == 1:
            self.history.record(*moved[0][:2], cat.id, s["mode"])
        elif moved:
            self.history.record_batch(moved)
        n = len(moved)
        msg = f"{n} photo{'s' if n > 1 else ''} triée{'s' if n > 1 else ''} vers {cat.name}"
        if skipped:
            msg += f" — {skipped} doublon(s) ignoré(s)"
        if errors:
            msg += f" — {errors} erreur(s) : {last_error}"
        self.library.flash(msg, "error" if errors and not n else "ok")
        self.library.set_photos(self._remaining())
        self.refresh()

    def _previous(self) -> None:
        if self._in_sort():
            self.model.previous()
            self.refresh()

    def _skip(self) -> None:
        if self._in_sort() and self.model.current() is not None:
            self.model.skip()
            self.refresh()

    def _in_work(self) -> bool:
        return self.sidebar.current() in (IDX_SORT, IDX_LIB) and QApplication.activeModalWidget() is None

    def _undo(self) -> None:
        if self._in_work():
            self.do_undo()

    def _redo(self) -> None:
        if self._in_work():
            self.do_redo()

    def do_undo(self) -> bool:
        """Annule la dernière opération ou le dernier lot (historique persistant, même d'une session à l'autre)."""
        try:
            entries = undo_last(self.history)
        except fm.FileOperationError as e:
            self.notify(str(e), "error")
            return False
        if not entries:
            self.notify("Rien à annuler.", "")
            return False
        first = None
        for e in entries:
            if e.mode == "rename":  # la photo reste dans la file, elle retrouve son ancien nom
                self.model.rename_path(e.dst, e.restored or e.src)
                continue
            idx = self.model.restore(e.src, e.category or "", e.restored)
            if idx is not None:
                first = idx if first is None else min(first, idx)
        if first is not None:
            self.model.go_to(first)
        n = len(entries)
        self._after_history_change()
        self.notify(f"{n} photos restaurées." if n > 1 else f"« {entries[0].src.name} » restaurée.", "ok")
        return True

    def do_redo(self) -> bool:
        """Rétablit la dernière opération (ou le dernier lot) annulée."""
        try:
            entries = redo_last(self.history)
        except fm.FileOperationError as e:
            self.notify(str(e), "error")
            return False
        if not entries:
            self.notify("Rien à rétablir.", "")
            return False
        for e in entries:
            if e.mode == "rename":
                self.model.rename_path(e.src, e.dst)
            else:
                self.model.reapply(e.src, e.category or "")
        self._after_history_change()
        self.notify(f"{len(entries)} opération(s) rétablie(s).", "ok")
        return True

    def _after_history_change(self) -> None:
        self.refresh()
        if self.sidebar.current() == IDX_LIB:
            self.library.set_photos(self._remaining())

    def show_history(self) -> None:
        if QApplication.activeModalWidget():
            return
        HistoryDialog(self.history, self.cfg, self.do_undo, self.do_redo, self).exec()
        self._after_history_change()

    def _on_filter(self, matched, text: str) -> None:
        count = self.model.set_allowed(matched)
        self.sort_page.set_filter_chip(f"Filtre actif : {text}  ({count} photos)" if matched is not None else "")
        self.library.set_photos(self._remaining())
        self.refresh()

    # ----- tri par date et renommage en lot (aperçu obligatoire, puis confirmation) -----
    def _target_photos(self) -> list[Path]:
        """Sélection de la grille si elle existe, sinon toutes les photos restantes de la file."""
        if self.sidebar.current() == IDX_LIB:
            selection = self.library.selected()
            if selection:
                return selection
        return self._remaining()

    def _tool_ready(self, setting: str, label: str) -> bool:
        if QApplication.activeModalWidget():
            return False
        if not self.cfg.settings.get(setting, True):
            self.notify(f"{label} est désactivé dans Réglages.", "")
            return False
        if not self.model.total or not self._target_photos():
            self.notify("Ouvrez d'abord un dossier contenant des photos.", "")
            return False
        return True

    def show_date_sorter(self) -> None:
        if not self._tool_ready("date_sort", "Le tri par date"):
            return
        dlg = DateSorterDialog(self._target_photos(), self.src_dir, self.dst_dir, self.cfg.settings, self)
        if dlg.exec() and dlg.plan:
            self.cfg.settings.update(dlg.choices())
            self.cfg.save_settings()
            self._apply_date_plan(dlg.plan)

    def show_batch_rename(self) -> None:
        if not self._tool_ready("batch_rename", "Le renommage en lot"):
            return
        dlg = BatchRenameDialog(self._target_photos(), self.cfg.settings, self)
        if dlg.exec() and dlg.plan:
            self.cfg.settings.update(dlg.choices())
            self.cfg.save_settings()
            self._apply_rename_plan(dlg.plan)

    def _apply_date_plan(self, plan) -> None:
        """Plan confirmé. Chaque photo est une entrée d'historique individuelle (un Ctrl+Z chacune)."""
        done, errors = execute_plan(plan)
        for op, dst in done:
            idx = self.model.index_of(op.src)
            if idx is not None:
                self.model.register_at(idx, dst, "", "move")
        self.history.record_many([(op.src, dst, None, "move") for op, dst in done])
        msg = f"{len(done)} photo(s) rangée(s) par date"
        if errors:
            msg += f" — {len(errors)} erreur(s) : {errors[0][1]}"
        self._after_tool(msg, "error" if errors and not done else "ok")

    def _apply_rename_plan(self, plan) -> None:
        """Plan confirmé. Tout le renommage forme UN lot : un seul Ctrl+Z le défait."""
        done, errors = execute_plan(plan)
        for op, dst in done:
            self.model.rename_path(op.src, dst)
        if done:
            self.history.record_batch([(op.src, dst, None, "rename") for op, dst in done])
        msg = f"{len(done)} photo(s) renommée(s)"
        if errors:
            msg += f" — {len(errors)} erreur(s) : {errors[0][1]}"
        self._after_tool(msg, "error" if errors and not done else "ok")

    def _after_tool(self, msg: str, tone: str) -> None:
        self.refresh()
        if self.sidebar.current() == IDX_LIB:
            self.library.set_photos(self._remaining())
        self.notify(msg, tone)

    # ------------------------------------------------------------- affichage
    def refresh(self) -> None:
        m, sp = self.model, self.sort_page
        cur = m.current()
        if cur is not None:
            sp.viewer.show_photo(cur)
            sp.viewer.prefetch([m.next_path(), m.previous_path()])
        elif m.allowed is not None and not m.allowed:
            sp.viewer.show_message("Aucune photo ne correspond au filtre")
        else:
            sp.viewer.show_message("Tri terminé !" if m.finished() else "Aucune photo")
        st = m.stats()
        cats = {c.id: c.name for c in self.cfg.categories()}
        pos, total = m.position()
        text = f"Traitées : {st['processed']}   ·   Restantes : {st['remaining']}   ·   Catégories : {len(cats)}"
        parts = [f"{cats[cid]} : {n}" for cid, n in st["counts"].items() if n and cid in cats]
        sp.nav.update_state(pos, total, text, "   ·   ".join(parts), bool(self.history.last_undoable()))
        if self.sidebar.current() == IDX_SORT:
            self._show_current_info()
        self._refresh_dashboard()
        self._update_status()

    def _show_current_info(self) -> None:
        self.info.show_photo(self.model.current())

    def _refresh_dashboard(self) -> None:
        cfg = self.cfg.settings
        self.dashboard.set_stats(self.model.stats(), self.cfg.categories())
        self.dashboard.set_recent(cfg.get("recent_folders", []))
        self.dashboard.set_sessions(cfg.get("sessions", []))

    def _update_status(self, selected: int = 0) -> None:
        page, st = self.sidebar.current(), self.model.stats()
        if page == IDX_SORT:
            state = "Tri terminé" if self.model.finished() else "Tri en cours"
        elif page == IDX_LIB:
            state = f"{selected} sélectionnée(s)" if selected else "Bibliothèque"
        else:
            state = "Prêt" if not st["total"] else "Session ouverte"
        self.status.update_state(state, st["scope_done"], st["scope_total"], HINTS.get(page, ""))

    def notify(self, text: str, tone: str = "") -> None:
        if self.sidebar.current() == IDX_LIB:
            self.library.flash(text, tone or "")
            return
        b = self.sort_page.banner
        b.setText(text)
        theme.set_tone(b, tone)
        b.show()
        self._banner_timer.start()

    def show_about(self) -> None:
        QMessageBox.about(self, "À propos",
                          f"<h3>{APP_TITLE} {VERSION}</h3><p>Tri rapide de photos, catégories personnalisables.</p>"
                          f"<p>Conçu par <b>{AUTHOR}</b><br>© {YEAR} — Tous droits réservés.</p>")

    # -------------------------------------------------------------- réglages
    def _setting_changed(self, key: str, value) -> None:
        if key == "clear_cache":  # action, pas un réglage persistant
            n = self.thumbs.clear()
            self.notify(f"Cache vidé : {n} miniature(s) supprimée(s).", "ok")
            self.library.grid.photo_model.set_px(self.library.grid.photo_model._px)
            return
        self.cfg.set(key, value)
        s = self.cfg.settings
        if key in ("palette", "accent"):
            theme.set_palette(s.get("palette", "hyperos"), s.get("accent"))
            theme.apply(QApplication.instance())
            QApplication.instance().setWindowIcon(icons.app_icon())
            for w in self.findChildren(QWidget):
                w.update()
            self.shell.update()
        elif key == "animated":
            self.shell.set_animated(bool(value))
        elif key == "animations":
            self.stack.animate = bool(value)
        elif key == "thumb_size":
            self.library.size_ctl.set_value(value)
            self.library.grid.set_thumb_px(int(value))
        elif key == "grid_columns":
            self.library.cols_ctl.set_value(value)
            self.library.set_columns(int(value))
        elif key == "cache_max_mb":
            self.thumbs.max_bytes = int(value) * 1024 * 1024
            self.thumbs.trim()
        elif key == "info_panel":
            self._update_panels()

    # ---------------------------------------------------------------- fenêtre
    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if self._grip is not None:
            g = self._grip
            g.move(self.shell.width() - g.width() - 6, self.shell.height() - g.height() - 6)

    def changeEvent(self, event) -> None:
        super().changeEvent(event)
        if self.native:
            return
        if event.type() == QEvent.Type.WindowStateChange:
            full = self.isMaximized() or self.isFullScreen()
            self.shell.set_radius(0 if full else CORNER_RADIUS)
            self.titlebar.refresh_state()

    def closeEvent(self, event) -> None:
        self._record_session()
        self.cfg.save_settings()
        self.history.close()
        super().closeEvent(event)
