"""Navigation, progression et statistiques (boutons de verre)."""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget

from widgets.controls import GlassButton


class NavigationBar(QWidget):
    previous = Signal()
    skip = Signal()
    undo = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.btn_prev = GlassButton("Précédente", "default", "arrow-left")
        self.btn_undo = GlassButton("Annuler", "ghost", "undo")
        self.btn_skip = GlassButton("Passer", "default", "arrow-right")
        for b in (self.btn_prev, self.btn_undo, self.btn_skip):
            b.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.progress = QLabel("")
        self.progress.setObjectName("progress")
        self.progress.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.stats = QLabel("")
        self.stats.setObjectName("hint")
        self.stats.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.breakdown = QLabel("")
        self.breakdown.setObjectName("muted")
        self.breakdown.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.breakdown.setWordWrap(True)

        row = QHBoxLayout()
        row.addWidget(self.btn_prev)
        row.addWidget(self.btn_undo)
        row.addStretch(1)
        row.addWidget(self.progress)
        row.addStretch(1)
        row.addWidget(self.btn_skip)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(6)
        lay.addLayout(row)
        lay.addWidget(self.stats)
        lay.addWidget(self.breakdown)
        self.btn_prev.clicked.connect(self.previous)
        self.btn_skip.clicked.connect(self.skip)
        self.btn_undo.clicked.connect(self.undo)

    def update_state(self, pos: int, total: int, stats_text: str, breakdown: str, can_undo: bool) -> None:
        self.progress.setText(f"Photo {pos} / {total}")
        self.stats.setText(stats_text)
        self.breakdown.setText(breakdown)
        self.btn_undo.setEnabled(can_undo)
