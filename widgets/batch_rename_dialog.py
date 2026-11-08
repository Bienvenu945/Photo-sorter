"""Renommer en lot (Ctrl+B) : modèle de nom avec variables, aperçu obligatoire, conflits résolus automatiquement."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import QLabel

from services.batch_ops import VARIABLES, PlannedOp, plan_rename, validate_template
from widgets.controls import GlassCombo, GlassLine
from widgets.plan_dialog import PlanDialog

EXAMPLES = ["{date}_{counter}.{ext}", "{annee}-{mois}_{counter}", "{camera}_{counter}", "{date}_{heure}_{original}"]


class BatchRenameDialog(PlanDialog):
    def __init__(self, photos: list[Path], settings: dict, parent=None) -> None:
        super().__init__("Renommer en lot",
                         "Aperçu (dry-run) : aucun fichier n'est modifié tant que vous n'avez pas cliqué sur « Renommer ». "
                         "Si un nom existe déjà, un suffixe _1, _2… est ajouté.", "Renommer", photos, parent)
        caption = QLabel("Modèle de nom")
        caption.setObjectName("muted")
        self.template = GlassLine("{date}_{counter}.{ext}")
        self.template.set_value(settings.get("rename_template", EXAMPLES[0]))
        self.examples = GlassCombo([("Exemples…", "")] + [(e, e) for e in EXAMPLES], width=260)
        self.examples.activated.connect(self._pick_example)
        hint = QLabel("Variables : " + "  ".join("{%s}" % v for v in VARIABLES) + "    ({counter:3} = 3 chiffres)")
        hint.setObjectName("hint")
        hint.setWordWrap(True)
        for w in (caption, self.template, self.examples, hint):
            self.options.addWidget(w)
        self.template.changed.connect(lambda _v: self.schedule())
        self.start()

    def _pick_example(self, index: int) -> None:
        value = self.examples.itemData(index)
        if value:
            self.template.set_value(value)
            self.schedule()  # set_value() est silencieux : on relance l'aperçu
        self.examples.setCurrentIndex(0)

    def choices(self) -> dict:
        return {"rename_template": self.template.value().strip()}

    def compute(self, progress) -> list[PlannedOp] | None:
        template = self.template.value().strip()
        validate_template(template)  # message d'erreur immédiat, sans lire les fichiers
        metas = self.metas(progress, "exif")
        return None if metas is None else plan_rename(metas, template)
