"""Page de base : défilement, titre, cartes de verre."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QLabel, QScrollArea, QVBoxLayout, QWidget

from widgets.glass import GlassCard, SettingRow


class BasePage(QScrollArea):
    TITLE = ""
    SUBTITLE = ""

    def __init__(self, cfg=None) -> None:
        super().__init__()
        self.cfg = cfg
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setAutoFillBackground(False)
        self.viewport().setAutoFillBackground(False)
        body = QWidget()
        body.setAutoFillBackground(False)
        self._v = QVBoxLayout(body)
        self._v.setContentsMargins(2, 2, 14, 22)
        self._v.setSpacing(18)
        head = QVBoxLayout()
        head.setSpacing(4)
        title = QLabel(self.TITLE)
        title.setObjectName("pageTitle")
        head.addWidget(title)
        if self.SUBTITLE:
            sub = QLabel(self.SUBTITLE)
            sub.setObjectName("pageSub")
            sub.setWordWrap(True)
            head.addWidget(sub)
        self._v.addLayout(head)
        self._v.addSpacing(4)
        self.setWidget(body)
        self.build()
        self._v.addStretch(1)

    def build(self) -> None: ...

    def on_enter(self) -> None: ...

    def card(self, title: str | None = None, subtitle: str | None = None) -> GlassCard:
        c = GlassCard(title, subtitle)
        self._v.addWidget(c)
        return c

    @staticmethod
    def row(card: GlassCard, title: str, control: QWidget | None = None, hint: str | None = None,
            stacked: bool = False) -> SettingRow:
        r = SettingRow(title, control, hint, stacked)
        card.add_row(r)
        return r
