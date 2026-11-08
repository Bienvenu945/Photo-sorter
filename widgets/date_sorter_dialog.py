"""Tri automatique par date (Ctrl+R) : aperçu des dossiers AAAA/MM - Mois/AAAA-MM-JJ avant tout déplacement."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import QLabel

from services.batch_ops import PlannedOp, plan_date_sort
from widgets.controls import GlassCombo, Segmented
from widgets.plan_dialog import PlanDialog


class DateSorterDialog(PlanDialog):
    def __init__(self, photos: list[Path], src_root: Path, dst_root: Path | None, settings: dict, parent=None) -> None:
        super().__init__("Trier par date",
                         "Les photos sont rangées dans des dossiers par date. Rien n'est déplacé tant que vous n'avez "
                         "pas cliqué sur « Trier ».", "Trier", photos, parent)
        self.roots = {"src": Path(src_root), "dst": Path(dst_root) if dst_root else None}
        self.source = Segmented([("EXIF", "exif"), ("Modification du fichier", "mtime"), ("Nom du fichier", "filename")])
        self.structure = Segmented([("Année / Mois / Jour", "ymd"), ("Année / Mois", "ym")])
        self.dest = GlassCombo([("Dossier source", "src")] + ([("Dossier destination", "dst")] if dst_root else []),
                               width=240)
        self.source.set_value(settings.get("date_source", "exif"))
        self.structure.set_value(settings.get("date_structure", "ymd"))
        self.dest.set_value("src")
        for caption, widget in (("Source de la date", self.source), ("Structure des dossiers", self.structure),
                                ("Où ranger les dossiers", self.dest)):
            label = QLabel(caption)
            label.setObjectName("muted")
            self.options.addWidget(label)
            self.options.addWidget(widget)
            widget.changed.connect(lambda _v: self.schedule())
        self.start()

    def choices(self) -> dict:
        return {"date_source": self.source.value(), "date_structure": self.structure.value()}

    def root(self) -> Path:
        return self.roots.get(self.dest.value()) or self.roots["src"]

    def compute(self, progress) -> list[PlannedOp] | None:
        metas = self.metas(progress, self.source.value())
        return None if metas is None else plan_date_sort(metas, self.root(), self.structure.value())

    def describe(self, op: PlannedOp) -> str:
        try:
            where = op.dst.parent.relative_to(self.root())
        except ValueError:
            where = op.dst.parent
        return f"{op.src.name}  →  {where}/{op.dst.name}"
