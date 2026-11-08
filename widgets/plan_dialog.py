"""Base des fenêtres « aperçu puis confirmation » : l'aperçu (dry-run) est OBLIGATOIRE avant toute modification."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QTimer
from PySide6.QtGui import QBrush
from PySide6.QtWidgets import QDialog, QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QVBoxLayout

import theme
from services.batch_ops import PlannedOp, summarize
from services.date_extractor import PhotoMeta, read_meta
from widgets.background import BackgroundCall
from widgets.controls import GlassButton

PREVIEW_MAX = 200


class PlanDialog(QDialog):
    """Sous-classes : ajoutent leurs options dans ``self.options`` et implémentent ``compute`` (exécuté hors thread UI)."""

    def __init__(self, title: str, subtitle: str, apply_label: str, photos: list[Path], parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setModal(True)
        self.setMinimumSize(760, 640)
        self.photos = list(photos)
        self.plan: list[PlannedOp] = []       # plan confirmé (rempli seulement si l'utilisateur valide)
        self._plan: list[PlannedOp] = []      # dernier aperçu calculé
        self._cache: dict[tuple[Path, str], PhotoMeta] = {}
        self._call = BackgroundCall(self)
        self._call.progress.connect(lambda d, t: self.status.setText(f"Lecture des métadonnées… {d} / {t}"))
        self._call.result.connect(self._on_result)
        self._call.failed.connect(self._on_failed)
        self._timer = QTimer(self, singleShot=True, interval=250)  # anti-rebond
        self._timer.timeout.connect(self._recompute)

        head = QLabel(title)
        head.setObjectName("pageTitle")
        sub = QLabel(subtitle)
        sub.setObjectName("pageSub")
        sub.setWordWrap(True)
        self.options = QVBoxLayout()
        self.options.setSpacing(10)
        self.summary = QLabel("")
        self.summary.setObjectName("progress")
        self.status = QLabel("")
        self.status.setObjectName("hint")
        self.preview = QListWidget()
        self.b_cancel = GlassButton("Annuler", "default")
        self.b_apply = GlassButton(apply_label, "primary")
        self.b_apply.setEnabled(False)  # activé uniquement quand un aperçu valide est affiché
        self.b_cancel.clicked.connect(self.reject)
        self.b_apply.clicked.connect(self._confirm)
        row = QHBoxLayout()
        row.addStretch(1)
        row.addWidget(self.b_cancel)
        row.addWidget(self.b_apply)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(26, 22, 26, 20)
        lay.setSpacing(10)
        lay.addWidget(head)
        lay.addWidget(sub)
        lay.addLayout(self.options)
        lay.addWidget(self.summary)
        lay.addWidget(self.status)
        lay.addWidget(self.preview, 1)
        lay.addLayout(row)

    # ----- à surcharger -----
    def compute(self, progress) -> list[PlannedOp]:
        raise NotImplementedError

    def describe(self, op: PlannedOp) -> str:
        return f"{op.src.name}  →  {op.dst.name}"

    # ----- utilitaires pour compute (thread de travail) -----
    def metas(self, progress, preference: str = "exif") -> list[PhotoMeta] | None:
        out, total = [], len(self.photos)
        for i, p in enumerate(self.photos, 1):
            m = self._cache.get((p, preference))
            if m is None:
                try:
                    m = read_meta(p, preference)
                except OSError:
                    continue  # fichier disparu
                self._cache[(p, preference)] = m
            out.append(m)
            if (i % 25 == 0 or i == total) and not progress(i, total):
                return None  # annulé : un calcul plus récent a pris le relais
        return out

    # ----- cycle de vie -----
    def start(self) -> None:
        self.schedule()

    def schedule(self) -> None:
        """À appeler à chaque changement d'option : invalide l'aperçu puis recalcule."""
        self.b_apply.setEnabled(False)
        self.status.setText("Calcul de l'aperçu…")
        self._timer.start()

    def _recompute(self) -> None:
        self._call.submit(self.compute)

    def _on_result(self, plan) -> None:
        if plan is None:
            return
        self._plan = plan
        s = summarize(plan)
        self.preview.clear()
        for op in plan[:PREVIEW_MAX]:
            text = self.describe(op)
            if op.skipped:
                text += "    (inchangé)"
            elif op.conflict:
                text += "    (nom déjà pris : suffixe ajouté)"
            item = QListWidgetItem(text)
            if op.skipped:
                item.setForeground(QBrush(theme.fg(100)))
            self.preview.addItem(item)
        if len(plan) > PREVIEW_MAX:
            self.preview.addItem(QListWidgetItem(f"… et {len(plan) - PREVIEW_MAX} autres"))
        self.summary.setText(f"{s['total']} photo(s) concernée(s)  ·  {s['to_do']} à modifier  ·  "
                             f"{s['skipped']} inchangée(s)  ·  {s['conflicts']} conflit(s) résolu(s)")
        self.status.setText("Aperçu à jour : aucun fichier n'a été modifié.")
        self.status.setStyleSheet("")
        self.b_apply.setEnabled(s["to_do"] > 0)

    def _on_failed(self, message: str) -> None:
        self._plan = []
        self.preview.clear()
        self.summary.setText("")
        self.status.setText(message)
        self.status.setStyleSheet("color: #fca5a5;")
        self.b_apply.setEnabled(False)

    def _confirm(self) -> None:
        self.plan = list(self._plan)
        self.accept()
