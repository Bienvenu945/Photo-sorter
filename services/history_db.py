"""Historique persistant (SQLite, stdlib) avec annuler / rétablir, y compris par lot."""
from __future__ import annotations

import logging
import sqlite3
import threading
import time
import uuid
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from models import SortOperation
from services import file_manager as fm

logger = logging.getLogger(__name__)

DEFAULT_LIMIT = 500
_SCHEMA = """
CREATE TABLE IF NOT EXISTS operations (
    id INTEGER PRIMARY KEY,
    timestamp INTEGER NOT NULL,
    src TEXT NOT NULL,
    dst TEXT NOT NULL,
    category TEXT,
    mode TEXT,
    batch_id TEXT,
    undone INTEGER DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_timestamp ON operations(timestamp);
CREATE INDEX IF NOT EXISTS idx_batch ON operations(batch_id);
"""


@dataclass
class HistoryEntry:
    id: int
    timestamp: int
    src: Path
    dst: Path
    category: str | None
    mode: str
    batch_id: str | None
    undone: bool
    restored: Path | None = None  # chemin où la photo est revenue après annulation

    def to_operation(self) -> SortOperation:
        return SortOperation(self.src, self.dst, self.category or "", float(self.timestamp), self.mode)


def default_history_path() -> Path:
    from config import default_config_dir

    return default_config_dir() / "history.db"


class HistoryDB:
    """Chaque opération est enregistrée immédiatement ; au-delà de ``limit`` les plus anciennes sont purgées."""

    def __init__(self, path: Path | str | None = None, limit: int = DEFAULT_LIMIT) -> None:
        self.path = Path(path) if path is not None else default_history_path()
        if str(self.path) != ":memory:":
            self.path.parent.mkdir(parents=True, exist_ok=True)
        self.limit = int(limit)
        self._lock = threading.RLock()
        self._db = sqlite3.connect(str(self.path), check_same_thread=False)
        self._db.row_factory = sqlite3.Row
        self._db.executescript(_SCHEMA)
        self.prune()

    def close(self) -> None:
        with self._lock:
            self._db.close()

    # ---------- écriture ----------
    def record(self, src: Path, dst: Path, category: str | None, mode: str,
               batch_id: str | None = None, timestamp: int | None = None) -> int:
        """Enregistre une opération. Toute nouvelle opération invalide la pile « rétablir »."""
        with self._lock, self._db:
            self._db.execute("DELETE FROM operations WHERE undone = 1")
            cur = self._db.execute(
                "INSERT INTO operations (timestamp, src, dst, category, mode, batch_id) VALUES (?,?,?,?,?,?)",
                (int(timestamp if timestamp is not None else time.time()), str(src), str(dst), category, mode,
                 batch_id))
            row_id = int(cur.lastrowid)
        self.prune()
        return row_id

    def record_batch(self, items: Iterable[tuple[Path, Path, str | None, str]]) -> str:
        """Enregistre un lot (src, dst, catégorie, mode) : annulable d'un seul Ctrl+Z. Retourne le batch_id."""
        batch_id = uuid.uuid4().hex
        now = int(time.time())
        with self._lock, self._db:
            self._db.execute("DELETE FROM operations WHERE undone = 1")
            self._db.executemany(
                "INSERT INTO operations (timestamp, src, dst, category, mode, batch_id) VALUES (?,?,?,?,?,?)",
                [(now, str(s), str(d), c, m, batch_id) for s, d, c, m in items])
        self.prune()
        return batch_id

    def record_many(self, items: Iterable[tuple[Path, Path, str | None, str]]) -> list[int]:
        """Enregistre des opérations INDIVIDUELLES (un Ctrl+Z chacune) en une seule transaction."""
        now = int(time.time())
        ids: list[int] = []
        with self._lock, self._db:
            self._db.execute("DELETE FROM operations WHERE undone = 1")
            for s, d, c, m in items:
                cur = self._db.execute(
                    "INSERT INTO operations (timestamp, src, dst, category, mode, batch_id) VALUES (?,?,?,?,?,NULL)",
                    (now, str(s), str(d), c, m))
                ids.append(int(cur.lastrowid))
        self.prune()
        return ids

    def set_undone(self, ids: Iterable[int], undone: bool) -> None:
        ids = list(ids)
        if not ids:
            return
        with self._lock, self._db:
            self._db.executemany("UPDATE operations SET undone = ? WHERE id = ?", [(int(undone), i) for i in ids])

    def update_dst(self, entry_id: int, dst: Path) -> None:
        with self._lock, self._db:
            self._db.execute("UPDATE operations SET dst = ? WHERE id = ?", (str(dst), entry_id))

    def prune(self) -> None:
        with self._lock, self._db:
            self._db.execute(
                "DELETE FROM operations WHERE id NOT IN (SELECT id FROM operations ORDER BY id DESC LIMIT ?)",
                (self.limit,))

    def clear(self) -> None:
        with self._lock, self._db:
            self._db.execute("DELETE FROM operations")

    # ---------- lecture ----------
    @staticmethod
    def _entry(row: sqlite3.Row) -> HistoryEntry:
        return HistoryEntry(row["id"], row["timestamp"], Path(row["src"]), Path(row["dst"]), row["category"],
                            row["mode"] or "move", row["batch_id"], bool(row["undone"]))

    def _group(self, first: sqlite3.Row | None, undone: int, newest_first: bool) -> list[HistoryEntry]:
        if first is None:
            return []
        if first["batch_id"] is None:
            return [self._entry(first)]
        order = "DESC" if newest_first else "ASC"
        rows = self._db.execute(
            f"SELECT * FROM operations WHERE batch_id = ? AND undone = ? ORDER BY id {order}",
            (first["batch_id"], undone)).fetchall()
        return [self._entry(r) for r in rows]

    def last_undoable(self) -> list[HistoryEntry]:
        """Dernière opération (ou dernier lot) non annulée, dans l'ordre d'annulation (récent → ancien)."""
        with self._lock:
            row = self._db.execute("SELECT * FROM operations WHERE undone = 0 ORDER BY id DESC LIMIT 1").fetchone()
            return self._group(row, 0, newest_first=True)

    def last_redoable(self) -> list[HistoryEntry]:
        """Dernière opération (ou lot) annulée, dans l'ordre de ré-application (ancien → récent)."""
        with self._lock:
            row = self._db.execute("SELECT * FROM operations WHERE undone = 1 ORDER BY id ASC LIMIT 1").fetchone()
            return self._group(row, 1, newest_first=False)

    def entries(self, limit: int = 100, include_undone: bool = True) -> list[HistoryEntry]:
        """Opérations les plus récentes en premier (pour la fenêtre Historique)."""
        sql = "SELECT * FROM operations " + ("" if include_undone else "WHERE undone = 0 ") + "ORDER BY id DESC LIMIT ?"
        with self._lock:
            return [self._entry(r) for r in self._db.execute(sql, (limit,)).fetchall()]

    def count(self) -> int:
        with self._lock:
            return int(self._db.execute("SELECT COUNT(*) FROM operations").fetchone()[0])

    # ---------- sécurité ----------
    @staticmethod
    def check_undoable(group: Iterable[HistoryEntry]) -> list[str]:
        """Messages d'avertissement si un fichier a été déplacé/supprimé à la main entre-temps."""
        return [f"« {e.dst.name} » est introuvable (déplacé ou supprimé) : annulation bloquée."
                for e in group if not e.dst.exists()]


def undo_last(db: HistoryDB) -> list[HistoryEntry]:
    """Annule la dernière opération ou le dernier lot. Retourne les entrées annulées ([] s'il n'y en a pas).

    Lève ``FileOperationError`` si un fichier a disparu (rien n'est alors modifié) ou si une
    opération échoue en cours de lot (les opérations déjà annulées restent marquées comme telles).
    """
    group = db.last_undoable()
    if not group:
        return []
    problems = db.check_undoable(group)
    if problems:
        raise fm.FileOperationError(" ".join(problems))
    done: list[HistoryEntry] = []
    try:
        for e in group:
            e.restored = fm.undo(e.to_operation())
            done.append(e)
    except fm.FileOperationError as err:
        db.set_undone((e.id for e in done), True)
        raise fm.FileOperationError(f"{err} ({len(done)}/{len(group)} annulées)") from err
    db.set_undone((e.id for e in done), True)
    return done


def redo_last(db: HistoryDB) -> list[HistoryEntry]:
    """Rétablit la dernière opération (ou lot) annulée."""
    group = db.last_redoable()
    if not group:
        return []
    done: list[HistoryEntry] = []
    try:
        for e in group:
            final = fm.redo(e.to_operation())
            if final != e.dst:
                db.update_dst(e.id, final)
                e.dst = final
            done.append(e)
    except fm.FileOperationError as err:
        db.set_undone((e.id for e in done), False)
        raise fm.FileOperationError(f"{err} ({len(done)}/{len(group)} rétablies)") from err
    db.set_undone((e.id for e in done), False)
    return done
