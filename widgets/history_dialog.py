"""Fenêtre d'historique : consulter, annuler, rétablir ou vider les opérations (persistantes)."""
from __future__ import annotations

from collections.abc import Callable
from datetime import datetime

from PySide6.QtCore import Qt
from PySide6.QtGui import QBrush
from PySide6.QtWidgets import QDialog, QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QMessageBox, QVBoxLayout

import theme
from config import ConfigManager
from services.history_db import HistoryDB
from widgets.controls import GlassButton

MODES = {"move": "déplacé", "copy": "copié", "rename": "renommé"}


class HistoryDialog(QDialog):
    def __init__(self, db: HistoryDB, cfg: ConfigManager, on_undo: Callable[[], bool], on_redo: Callable[[], bool],
                 parent=None) -> None:
        super().__init__(parent)
        self.db, self.cfg, self._undo, self._redo = db, cfg, on_undo, on_redo
        self.setWindowTitle("Historique")
        self.setModal(True)
        self.setMinimumSize(640, 520)
        title = QLabel("Historique des opérations")
        title.setObjectName("pageTitle")
        self.summary = QLabel("")
        self.summary.setObjectName("hint")
        self.list = QListWidget()
        b_undo = GlassButton("Annuler la dernière", "default", "undo")
        b_redo = GlassButton("Rétablir", "default", "arrow-right")
        b_clear = GlassButton("Vider l'historique", "danger")
        b_close = GlassButton("Fermer", "primary")
        b_undo.clicked.connect(lambda: self._act(self._undo))
        b_redo.clicked.connect(lambda: self._act(self._redo))
        b_clear.clicked.connect(self._clear)
        b_close.clicked.connect(self.accept)
        row = QHBoxLayout()
        for b in (b_undo, b_redo, b_clear):
            row.addWidget(b)
        row.addStretch(1)
        row.addWidget(b_close)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 22, 24, 20)
        lay.setSpacing(12)
        lay.addWidget(title)
        lay.addWidget(self.summary)
        lay.addWidget(self.list, 1)
        lay.addLayout(row)
        self.refresh()

    def refresh(self) -> None:
        self.list.clear()
        entries = self.db.entries(300)
        for e in entries:
            cat = self.cfg.category(e.category) if e.category else None
            name = cat.name if cat else ("(catégorie supprimée)" if e.category else "—")
            when = datetime.fromtimestamp(e.timestamp).strftime("%d/%m %H:%M")
            lot = "  · lot" if e.batch_id else ""
            text = f"{when}    {e.src.name}  →  {name}    ({MODES.get(e.mode, e.mode)}){lot}"
            if e.undone:
                text += "    [annulé]"
            item = QListWidgetItem(text)
            if e.undone:
                item.setForeground(QBrush(theme.fg(110)))
            self.list.addItem(item)
        self.summary.setText(f"{len(entries)} opération(s) enregistrée(s) — conservées d'une session à l'autre."
                             if entries else "Aucune opération enregistrée.")

    def _act(self, fn: Callable[[], bool]) -> None:
        fn()
        self.refresh()

    def _clear(self) -> None:
        if QMessageBox.question(self, "Vider l'historique",
                                "Supprimer tout l'historique ? Les photos déjà triées ne sont pas touchées, "
                                "mais ces opérations ne pourront plus être annulées.") == QMessageBox.StandardButton.Yes:
            self.db.clear()
            self.refresh()
