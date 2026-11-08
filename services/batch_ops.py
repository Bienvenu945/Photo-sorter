"""Planification (dry-run) et exécution du tri par date et du renommage en lot. Aucune dépendance Qt.

Principe : on CALCULE d'abord un plan (liste de ``PlannedOp``) sans toucher aux fichiers ; l'interface le montre à
l'utilisateur ; ``execute_plan`` ne s'exécute qu'après confirmation.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from pathlib import Path

from services import file_manager as fm
from services.date_extractor import PhotoMeta, date_folder

logger = logging.getLogger(__name__)

VARIABLES = ("date", "annee", "mois", "jour", "heure", "camera", "modele", "counter", "original", "ext")
DEFAULT_COUNTER_WIDTH = 4
_VAR = re.compile(r"\{(\w+)(?::(\d+))?\}")
_INVALID = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


class TemplateError(ValueError):
    """Modèle de nom invalide (message lisible par l'utilisateur)."""


@dataclass(frozen=True)
class PlannedOp:
    src: Path
    dst: Path
    conflict: bool = False   # le nom voulu existait : un suffixe _1, _2… a été ajouté
    skipped: bool = False    # rien à faire (déjà au bon endroit / bon nom)


# ---------------------------------------------------------------- modèles de noms
def validate_template(template: str) -> None:
    """Lève ``TemplateError`` si le modèle est vide, contient une variable inconnue ou une accolade isolée."""
    if not template.strip():
        raise TemplateError("Le modèle ne peut pas être vide.")
    if "/" in template or "\\" in template:
        raise TemplateError("Le modèle ne peut pas contenir de « / » ni de « \\ ».")
    for m in _VAR.finditer(template):
        if m.group(1) not in VARIABLES:
            raise TemplateError(f"Variable inconnue : {{{m.group(1)}}} (disponibles : {', '.join(VARIABLES)})")
        if m.group(2) and m.group(1) != "counter":
            raise TemplateError(f"Seule {{counter}} accepte une largeur (ex. {{counter:3}}).")
    if "{" in _VAR.sub("", template) or "}" in _VAR.sub("", template):
        raise TemplateError("Accolade isolée dans le modèle.")


def split_camera(camera: str | None) -> tuple[str, str]:
    """'Canon EOS 5D' -> ('Canon', 'EOS5D') ; inconnu -> ('inconnu', 'inconnu')."""
    parts = (camera or "").split()
    if not parts:
        return "inconnu", "inconnu"
    return parts[0], "".join(parts[1:]) or "inconnu"


def render_name(template: str, meta: PhotoMeta, counter: int) -> str:
    """Nom final pour une photo. Sans extension dans le modèle, celle de l'original est conservée."""
    validate_template(template)
    make, model = split_camera(meta.camera)
    d = meta.date
    values = {"date": d.strftime("%Y-%m-%d"), "annee": d.strftime("%Y"), "mois": d.strftime("%m"),
              "jour": d.strftime("%d"), "heure": d.strftime("%H-%M-%S"), "camera": make, "modele": model,
              "original": meta.path.stem, "ext": meta.path.suffix.lstrip(".")}

    def sub(m: re.Match) -> str:
        if m.group(1) == "counter":
            return str(counter).zfill(int(m.group(2)) if m.group(2) else DEFAULT_COUNTER_WIDTH)
        return values[m.group(1)]

    name = _INVALID.sub("_", _VAR.sub(sub, template)).strip().rstrip(". ")
    if not name:
        raise TemplateError("Le modèle produit un nom vide.")
    if not Path(name).suffix:
        name += meta.path.suffix
    return name


# ---------------------------------------------------------------- plans
class _Names:
    """Noms déjà pris par dossier (insensible à la casse), lus une seule fois."""

    def __init__(self) -> None:
        self._taken: dict[Path, set[str]] = {}

    def _load(self, folder: Path) -> set[str]:
        if folder not in self._taken:
            try:
                self._taken[folder] = {p.name.lower() for p in folder.iterdir()}
            except OSError:  # dossier pas encore créé
                self._taken[folder] = set()
        return self._taken[folder]

    def take(self, folder: Path, name: str, own: bool = False) -> tuple[str, bool]:
        """Réserve ``name`` dans ``folder`` ; ajoute _1, _2… s'il est pris. ``own`` : le fichier porte déjà ce nom."""
        taken = self._load(folder)
        if own:
            return name, False
        final, n = name, 0
        while final.lower() in taken:
            n += 1
            final = f"{Path(name).stem}_{n}{Path(name).suffix}"
        taken.add(final.lower())
        return final, n > 0


def plan_rename(metas: list[PhotoMeta], template: str, start: int = 1) -> list[PlannedOp]:
    """Aperçu du renommage en lot (compteur dans l'ordre de ``metas``). Ne modifie aucun fichier."""
    validate_template(template)
    names, plan = _Names(), []
    for i, meta in enumerate(metas, start):
        new = render_name(template, meta, i)
        folder = meta.path.parent
        if new.lower() == meta.path.name.lower():
            plan.append(PlannedOp(meta.path, meta.path, skipped=True))
            continue
        final, conflict = names.take(folder, new)
        plan.append(PlannedOp(meta.path, folder / final, conflict=conflict))
    return plan


def plan_date_sort(metas: list[PhotoMeta], dest_root: Path, structure: str = "ymd") -> list[PlannedOp]:
    """Aperçu du tri par date : ``dest_root/AAAA/MM - Mois/AAAA-MM-JJ/`` (ou ``AAAA-MM/``). Ne modifie rien."""
    names, plan = _Names(), []
    for meta in metas:
        folder = Path(dest_root) / date_folder(meta.date, structure)
        if folder.resolve() == meta.path.parent.resolve():
            plan.append(PlannedOp(meta.path, meta.path, skipped=True))
            continue
        final, conflict = names.take(folder, meta.path.name)
        plan.append(PlannedOp(meta.path, folder / final, conflict=conflict))
    return plan


def summarize(plan: list[PlannedOp]) -> dict[str, int]:
    return {"total": len(plan), "to_do": sum(not op.skipped for op in plan),
            "skipped": sum(op.skipped for op in plan), "conflicts": sum(op.conflict for op in plan)}


# ---------------------------------------------------------------- exécution
def execute_plan(plan: list[PlannedOp]) -> tuple[list[tuple[PlannedOp, Path]], list[tuple[PlannedOp, str]]]:
    """Applique un plan CONFIRMÉ. Retourne (réussites avec chemin final, erreurs avec message). Continue après une erreur."""
    done: list[tuple[PlannedOp, Path]] = []
    errors: list[tuple[PlannedOp, str]] = []
    for op in plan:
        if op.skipped:
            continue
        try:
            done.append((op, fm.move_to(op.src, op.dst)))
        except fm.FileOperationError as e:
            logger.warning("Plan : %s", e)
            errors.append((op, str(e)))
    return done, errors
