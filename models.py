"""Modèle métier : aucun code d'interface graphique ici."""
from __future__ import annotations

import logging
import re
import time
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".gif", ".tif", ".tiff"}


@dataclass
class Category:
    id: str
    name: str
    shortcut: str
    color: str = "#0a84ff"
    order: int = 0

    @classmethod
    def new(cls, name: str, shortcut: str, color: str = "#0a84ff") -> "Category":
        return cls(id=str(uuid.uuid4()), name=name, shortcut=shortcut, color=color)

    @classmethod
    def from_dict(cls, d: dict) -> "Category":
        return cls(
            id=str(d.get("id") or uuid.uuid4()),
            name=str(d.get("name", "")),
            shortcut=str(d.get("shortcut", "")),
            color=str(d.get("color") or "#0a84ff"),
            order=int(d.get("order", 0)),
        )

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class SortOperation:
    src: Path
    dst: Path
    category_id: str
    timestamp: float
    mode: str  # "move" ou "copy"
    index: int = -1


def _natural_key(p: Path):
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", p.name)]


class PhotoSorterModel:
    def __init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        self.photos: list[Path] = []
        self.index = 0
        self.done: set[int] = set()
        self.history: list[SortOperation] = []
        self.counts: dict[str, int] = {}
        self.ignored = 0
        self.allowed: set[int] | None = None  # filtre actif : indices autorisés
        self._pos: dict[Path, int] = {}

    # ---------- chargement ----------
    def load_folder(self, folder: Path, exclude_names=(), include_subdirs=False, exclude_dirs=()) -> int:
        self.reset()
        folder = Path(folder).resolve()
        excluded_names = {n.lower() for n in exclude_names}
        excluded_dirs = {Path(d).resolve() for d in exclude_dirs}
        found: list[Path] = []
        stack = [folder]
        while stack:  # parcours itératif : on ne garde que des chemins, jamais d'images en mémoire
            current = stack.pop()
            try:
                entries = list(current.iterdir())
            except OSError as e:
                logger.warning("Dossier illisible %s : %s", current, e)
                continue
            for p in entries:
                if p.is_dir():
                    if (include_subdirs and p.name.lower() not in excluded_names
                            and p.resolve() not in excluded_dirs):
                        stack.append(p)
                elif p.suffix.lower() in SUPPORTED_EXTENSIONS:
                    found.append(p)
                else:
                    self.ignored += 1
        self.photos = sorted(found, key=_natural_key)
        self._pos = {p: i for i, p in enumerate(self.photos)}
        logger.info("%d photo(s) chargée(s) depuis %s (%d ignorés)", len(self.photos), folder, self.ignored)
        return len(self.photos)

    # ---------- navigation ----------
    @property
    def total(self) -> int:
        return len(self.photos)

    def current(self) -> Path | None:
        return self.photos[self.index] if 0 <= self.index < self.total else None

    def finished(self) -> bool:
        return self.total > 0 and self.current() is None

    def _pending(self, start: int, step: int) -> int | None:
        i = start
        while 0 <= i < self.total:
            if i not in self.done and (self.allowed is None or i in self.allowed):
                return i
            i += step
        return None

    def next_path(self) -> Path | None:
        i = self._pending(self.index + 1, 1)
        return self.photos[i] if i is not None else None

    def previous_path(self) -> Path | None:
        i = self._pending(self.index - 1, -1)
        return self.photos[i] if i is not None else None

    def skip(self) -> None:
        j = self._pending(self.index + 1, 1)
        self.index = j if j is not None else self.total

    def previous(self) -> bool:
        j = self._pending(self.index - 1, -1)
        if j is None:
            return False
        self.index = j
        return True

    def position(self) -> tuple[int, int]:
        """(rang, total) dans la file courante ; avec un filtre : « Photo 3 / 47 »."""
        if self.allowed is None:
            return min(self.index + 1, self.total), self.total
        total = len(self.allowed)
        return min(sum(1 for i in self.allowed if i <= self.index), total), total

    def index_of(self, path: Path) -> int | None:
        return self._pos.get(Path(path))

    def set_allowed(self, paths) -> int:
        """Restreint la file de tri aux ``paths`` (None = aucun filtre). Retourne la taille de la file."""
        self.allowed = None if paths is None else {i for p in paths if (i := self.index_of(p)) is not None}
        j = self._pending(self.index, 1)
        if j is None:
            j = self._pending(0, 1)
        self.index = j if j is not None else self.total
        return self.total if self.allowed is None else len(self.allowed)

    def go_to(self, index: int) -> bool:
        """Place la photo active (refusé si déjà triée ou hors filtre)."""
        if 0 <= index < self.total and index not in self.done and (self.allowed is None or index in self.allowed):
            self.index = index
            return True
        return False

    # ---------- tri ----------
    def register(self, src: Path, dst: Path, category_id: str, mode: str) -> SortOperation:
        op = SortOperation(src, dst, category_id, time.time(), mode, self.index)
        self.history.append(op)
        self.done.add(self.index)
        self.counts[category_id] = self.counts.get(category_id, 0) + 1
        self.skip()
        return op

    def register_at(self, index: int, dst: Path, category_id: str, mode: str) -> SortOperation:
        """Enregistre le tri d'une photo quelconque (tri par lot depuis la grille)."""
        op = SortOperation(self.photos[index], dst, category_id, time.time(), mode, index)
        self.history.append(op)
        self.done.add(index)
        self.counts[category_id] = self.counts.get(category_id, 0) + 1
        if index == self.index:
            self.skip()
        return op

    def restore(self, src: Path, category_id: str, restored: Path | None = None) -> int | None:
        """Remet une photo dans la file après une annulation. Retourne son indice (None si inconnue)."""
        idx = self.index_of(src)
        if idx is None:
            return None
        self.done.discard(idx)
        self.counts[category_id] = max(0, self.counts.get(category_id, 1) - 1)
        if restored is not None and Path(restored) != Path(src):
            self.photos[idx] = Path(restored)
            self._pos.pop(Path(src), None)
            self._pos[Path(restored)] = idx
        return idx

    def rename_path(self, old: Path, new: Path) -> int | None:
        """Met à jour le chemin d'une photo renommée (la photo reste dans la file). Retourne son indice."""
        idx = self.index_of(old)
        if idx is None:
            return None
        self.photos[idx] = Path(new)
        self._pos.pop(Path(old), None)
        self._pos[Path(new)] = idx
        return idx

    def reapply(self, src: Path, category_id: str) -> int | None:
        """Marque de nouveau une photo comme triée (rétablir)."""
        idx = self.index_of(src)
        if idx is None:
            return None
        self.done.add(idx)
        self.counts[category_id] = self.counts.get(category_id, 0) + 1
        if idx == self.index:
            self.skip()
        return idx

    def discard_current(self) -> None:
        """Photo disparue : on l'écarte sans historique."""
        self.done.add(self.index)
        self.skip()

    def last_operation(self) -> SortOperation | None:
        return self.history[-1] if self.history else None

    def undo_last(self, restored: Path | None = None) -> SortOperation | None:
        if not self.history:
            return None
        op = self.history.pop()
        self.done.discard(op.index)
        self.counts[op.category_id] = max(0, self.counts.get(op.category_id, 1) - 1)
        if restored is not None and 0 <= op.index < self.total:
            self.photos[op.index] = restored
        self.index = op.index
        return op

    # ---------- statistiques ----------
    def stats(self) -> dict:
        processed = sum(self.counts.values())
        if self.allowed is None:
            scope_total, scope_done = self.total, len(self.done)
        else:
            scope_total, scope_done = len(self.allowed), len(self.done & self.allowed)
        return {"processed": processed, "remaining": scope_total - scope_done, "total": self.total,
                "scope_total": scope_total, "scope_done": scope_done, "counts": dict(self.counts)}
