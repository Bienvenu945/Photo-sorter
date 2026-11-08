"""Opérations sur les fichiers : déplacer, copier, annuler. Aucune dépendance Qt."""
from __future__ import annotations

import errno
import logging
import re
import shutil
from pathlib import Path

from models import SortOperation


logger = logging.getLogger(__name__)


class FileOperationError(Exception):
    pass


def safe_folder_name(name: str) -> str:
    return re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", name).strip(" .") or "_"


def unique_path(path: Path) -> Path:
    path = Path(path)
    if not path.exists():
        return path
    i = 1
    while True:
        cand = path.with_name(f"{path.stem}_{i}{path.suffix}")
        if not cand.exists():
            return cand
        i += 1


def transfer(src: Path, dest_dir: Path, mode: str = "move", policy: str = "rename") -> Path | None:
    """Retourne le chemin final, ou None si le fichier est ignoré (policy 'skip')."""
    src = Path(src).resolve()
    if not src.is_file():
        raise FileOperationError(f"Photo introuvable : {src.name}")
    dest_dir = Path(dest_dir)
    try:
        dest_dir.mkdir(parents=True, exist_ok=True)
    except PermissionError:
        raise FileOperationError(f"Permission refusée : {dest_dir}")
    except OSError as e:
        raise FileOperationError(f"Dossier inutilisable ({e.strerror}) : {dest_dir}")
    target = dest_dir / src.name
    if target.resolve() == src:
        raise FileOperationError("La source et la destination sont identiques.")
    if target.exists():
        if policy == "skip":
            logger.info("Skipped duplicate %s", target.name)
            return None
        if policy == "replace":
            try:
                target.unlink()
            except OSError as e:
                raise FileOperationError(f"Impossible de remplacer {target.name} : {e.strerror}")
        else:
            target = unique_path(target)
    try:
        if mode == "copy":
            shutil.copy2(src, target)
        else:
            shutil.move(str(src), str(target))
    except PermissionError:
        raise FileOperationError(f"Permission refusée pour {src.name}")
    except OSError as e:
        if e.errno == errno.ENOSPC:
            raise FileOperationError("Disque plein.")
        raise FileOperationError(f"Erreur sur {src.name} : {e.strerror or e}")
    verb = "Copied" if mode == "copy" else "Moved"
    logger.info("%s %s -> %s/%s", verb, src.name, dest_dir.name, target.name)
    return target


def undo(op: SortOperation) -> Path:
    """Annule une opération. Retourne le chemin où la photo se trouve de nouveau."""
    dst, src = Path(op.dst), Path(op.src)
    if not dst.exists():
        raise FileOperationError(f"{dst.name} a été déplacé ou supprimé : annulation impossible.")
    try:
        if op.mode == "copy":
            dst.unlink()
            logger.info("Undo copy: removed %s", dst.name)
            return src
        src.parent.mkdir(parents=True, exist_ok=True)
        target = unique_path(src)
        shutil.move(str(dst), str(target))
        logger.info("Undo move: %s -> %s", dst.name, target)
        return target
    except OSError as e:
        raise FileOperationError(f"Annulation impossible : {e.strerror or e}")


def redo(op: SortOperation) -> Path:
    """Ré-applique une opération annulée. Retourne le chemin final (renommé si le nom est pris)."""
    src, dst = Path(op.src), Path(op.dst)
    if not src.is_file():
        raise FileOperationError(f"{src.name} est introuvable : impossible de rétablir.")
    try:
        dst.parent.mkdir(parents=True, exist_ok=True)
        target = unique_path(dst)
        if op.mode == "copy":
            shutil.copy2(src, target)
        else:  # move / rename
            shutil.move(str(src), str(target))
    except OSError as e:
        raise FileOperationError(f"Rétablissement impossible : {e.strerror or e}")
    logger.info("Redo %s: %s -> %s", op.mode, src.name, target)
    return target


def move_to(src: Path, dst: Path) -> Path:
    """Déplace ou renomme ``src`` exactement vers ``dst`` (suffixe _1, _2… si le nom est pris). Retourne le chemin final."""
    src, dst = Path(src).resolve(), Path(dst)
    if not src.is_file():
        raise FileOperationError(f"Photo introuvable : {src.name}")
    try:
        dst.parent.mkdir(parents=True, exist_ok=True)
    except PermissionError:
        raise FileOperationError(f"Permission refusée : {dst.parent}")
    except OSError as e:
        raise FileOperationError(f"Dossier inutilisable ({e.strerror}) : {dst.parent}")
    if dst.resolve() == src:
        return src  # rien à faire
    target = unique_path(dst) if dst.exists() else dst
    try:
        shutil.move(str(src), str(target))
    except PermissionError:
        raise FileOperationError(f"Permission refusée pour {src.name}")
    except OSError as e:
        if e.errno == errno.ENOSPC:
            raise FileOperationError("Disque plein.")
        raise FileOperationError(f"Erreur sur {src.name} : {e.strerror or e}")
    logger.info("Moved %s -> %s", src.name, target)
    return target
