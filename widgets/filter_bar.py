"""Barre de commande des filtres : `:date 2026-08 :portrait`, autocomplétion (Tab), compteur en temps réel."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QEvent, QObject, QRunnable, Qt, QThreadPool, QTimer, Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget

import theme
from services.date_extractor import PhotoMeta, read_meta
from services.filter_parser import Filter, FilterError, complete, parse
from widgets.controls import GlassCombo, GlassLine

MAX_RECENT = 8
BATCH = 40


class _FilterLine(GlassLine):
    tabPressed = Signal()

    def event(self, e) -> bool:
        if e.type() == QEvent.Type.KeyPress and e.key() == Qt.Key.Key_Tab:
            self.tabPressed.emit()
            return True
        return super().event(e)


class _IndexSignals(QObject):
    batch = Signal(int, object, int, int)  # génération, {chemin: PhotoMeta}, faits, total


class _IndexTask(QRunnable):
    """Lit les métadonnées par paquets, hors du thread UI (annulable via la génération)."""

    def __init__(self, gen: int, paths: list[Path], owner: "FilterBar", signals: _IndexSignals) -> None:
        super().__init__()
        self.gen, self.paths, self.owner, self.signals = gen, paths, owner, signals

    def run(self) -> None:
        out: dict[Path, PhotoMeta] = {}
        total = len(self.paths)
        for i, path in enumerate(self.paths, 1):
            if self.owner.gen != self.gen:
                return
            try:
                out[path] = read_meta(path)
            except Exception:  # fichier disparu : ignoré
                pass
            if len(out) >= BATCH or i == total:
                self.signals.batch.emit(self.gen, out, i, total)
                out = {}


class FilterBar(QWidget):
    """Émet ``filterApplied(set[Path] | None, texte)`` ; None = aucun filtre."""

    filterApplied = Signal(object, str)
    recentChanged = Signal(object)

    def __init__(self, recent: list[str] | None = None, parent=None) -> None:
        super().__init__(parent)
        self.gen = 0
        self._paths: list[Path] = []
        self._metas: dict[Path, PhotoMeta] = {}
        self._indexed = 0
        self._base = 0
        self._wanted: Filter | None = None
        self._text = ""
        self._recent = list(recent or [])[:MAX_RECENT]
        self._signals = _IndexSignals()
        self._signals.batch.connect(self._on_batch)
        self._timer = QTimer(self, singleShot=True, interval=300)  # anti-rebond
        self._timer.timeout.connect(self._apply)

        self.edit = _FilterLine(":date 2026-08 :portrait    —    Tab pour compléter, :toutes pour retirer")
        self.edit.setMinimumHeight(38)
        self.edit.changed.connect(lambda _t: self._timer.start())
        self.edit.tabPressed.connect(self._complete)
        self.recent = GlassCombo(width=210)
        self.recent.activated.connect(lambda i: self._pick(self.recent.itemData(i)))
        self.chip = QLabel("FILTRE ACTIF")
        self.chip.setObjectName("pill")
        self.chip.hide()
        self.status = QLabel("")
        self.status.setObjectName("hint")
        self._fill_recent()

        row = QHBoxLayout()
        row.setSpacing(10)
        row.addWidget(self.edit, 1)
        row.addWidget(self.recent)
        row.addWidget(self.chip)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(4)
        lay.addLayout(row)
        lay.addWidget(self.status)

    # ----- API -----
    def set_session(self, paths: list[Path]) -> None:
        """Nouvelle liste de photos : l'index des métadonnées est réinitialisé et le filtre retiré."""
        self.gen += 1
        self._paths, self._metas, self._indexed, self._wanted = list(paths), {}, 0, None
        self.edit.set_value("")
        self.chip.hide()
        self.status.setText("")

    def clear(self) -> None:
        self.edit.set_value("")
        self._timer.stop()
        self._apply()

    def text(self) -> str:
        return self.edit.value().strip()

    @property
    def active(self) -> bool:
        return not self.chip.isHidden()

    # ----- interne -----
    def _fill_recent(self) -> None:
        self.recent.clear()
        self.recent.addItem("Filtres récents", "")
        for t in self._recent:
            self.recent.addItem(t, t)

    def _remember(self, text: str) -> None:
        if not text:
            return
        self._recent = [text] + [t for t in self._recent if t != text]
        self._recent = self._recent[:MAX_RECENT]
        self._fill_recent()
        self.recentChanged.emit(list(self._recent))

    def _pick(self, text: str) -> None:
        if text:
            self.edit.set_value(text)
            self._timer.stop()
            self._apply()
        self.recent.setCurrentIndex(0)

    def _complete(self) -> None:
        self.edit.set_value(complete(self.edit.value()))
        self.edit.setCursorPosition(len(self.edit.text()))
        self._timer.start()

    def _set_status(self, text: str, tone: str = "") -> None:
        self.status.setText(text)
        self.status.setStyleSheet(f"color: {'#fca5a5' if tone == 'error' else theme.current().accent_a};"
                                  if tone else "")

    def _apply(self) -> None:
        text = self.text()
        if not text:
            self._wanted, self._text = None, ""
            self.chip.hide()
            self._set_status("")
            self.filterApplied.emit(None, "")
            return
        try:
            flt = parse(text)
        except FilterError as e:
            self._set_status(str(e), "error")
            return
        if flt.is_empty:
            self._wanted = None
            self.chip.hide()
            self._set_status("")
            self.filterApplied.emit(None, "")
            return
        self._wanted, self._text = flt, text
        if self._indexed >= len(self._paths):
            self._compute()
        else:
            self._start_index()

    def _start_index(self) -> None:
        todo = [p for p in self._paths if p not in self._metas]
        self._set_status(f"Analyse des photos… {self._indexed} / {len(self._paths)}", "info")
        self.gen += 1  # annule une analyse en cours puis la relance sur ce qui manque
        QThreadPool.globalInstance().start(_IndexTask(self.gen, todo, self, self._signals))
        self._base = len(self._paths) - len(todo)

    def _on_batch(self, gen: int, metas: dict, done: int, total: int) -> None:
        if gen != self.gen:
            return
        self._metas.update(metas)
        self._indexed = self._base + done
        if self._indexed >= len(self._paths):
            if self._wanted is not None:
                self._compute()
        elif self._wanted is not None:
            self._set_status(f"Analyse des photos… {self._indexed} / {len(self._paths)}", "info")

    def _compute(self) -> None:
        if self._wanted is None:
            return
        flt = self._wanted
        matched = {p for p in self._paths if p in self._metas and flt.matches(self._metas[p])}
        self.chip.show()
        self._set_status(f"{len(matched)} / {len(self._paths)} photos correspondent  ·  {flt.describe()}", "info")
        self._remember(self._text)
        self.filterApplied.emit(matched, self._text)
