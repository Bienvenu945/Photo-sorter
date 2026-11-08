"""Configuration persistante : catégories (avec profils) et préférences."""
from __future__ import annotations

import json
import logging
import shutil
from pathlib import Path

from models import Category

logger = logging.getLogger(__name__)

APP_NAME = "PhotoSorterStudio"
APP_TITLE = "Photo Sorter Studio"
AUTHOR = "Bienvenu K.K"
YEAR = "2026"
VERSION = "2.0"
CREDIT = f"Conçu par {AUTHOR}  ·  © {YEAR}"
MAX_NAME_LEN = 40
RESERVED_SHORTCUTS = {"esc", "escape", "space", "left", "right", "return", "enter", "tab", "ctrl+z", "g", "f11", "ctrl+,", "ctrl+a", "ctrl+h", "ctrl+shift+z", "ctrl+r", "ctrl+b"}

DEFAULT_SETTINGS = {
    "palette": "hyperos",
    "accent": None,
    "animations": True,
    "thumb_size": 192,
    "info_panel": True,
    "view_mode": "grid",
    "sort_by": "name",
    "recent_folders": [],
    "recent_filters": [],
    "grid_columns": 4,
    "date_sort": True,
    "batch_rename": True,
    "date_source": "exif",
    "date_structure": "ymd",
    "rename_template": "{date}_{counter}.{ext}",
    "cache_max_mb": 500,
    "batch_sort": True,
    "batch_limit": 100,
    "grid_shortcut": True,
    "sessions": [],
    "animated": True,
    "mode": "move",
    "last_source_dir": None,
    "last_dest_dir": None,
    "exclude_subdirs": True,
    "include_subdirs": False,
    "duplicate_policy": "rename",
    "native_titlebar": False,
}


def default_config_dir() -> Path:
    try:
        from PySide6.QtCore import QStandardPaths
        p = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppConfigLocation)
        if p:
            return Path(p)
    except Exception:
        pass
    return Path.home() / ".config" / APP_NAME


def validate_categories(cats: list[Category]) -> list[str]:
    errors: list[str] = []
    names: set[str] = set()
    keys: set[str] = set()
    for c in cats:
        name = c.name.strip()
        if not name:
            errors.append("Le nom d'une catégorie ne peut pas être vide.")
        elif len(name) > MAX_NAME_LEN:
            errors.append(f"« {name[:15]}… » dépasse {MAX_NAME_LEN} caractères.")
        elif name.lower() in names:
            errors.append(f"Le nom « {name} » est déjà utilisé.")
        names.add(name.lower())
        sc = c.shortcut.strip().lower().replace(" ", "")
        if sc:
            if sc in RESERVED_SHORTCUTS:
                errors.append(f"Le raccourci « {c.shortcut} » est réservé.")
            elif sc in keys:
                errors.append(f"Le raccourci « {c.shortcut} » est déjà utilisé.")
            keys.add(sc)
        else:
            errors.append(f"La catégorie « {name or '?'} » n'a pas de raccourci.")
    return errors


class ConfigManager:
    def __init__(self, config_dir: Path | None = None) -> None:
        self.dir = Path(config_dir) if config_dir else default_config_dir()
        self.dir.mkdir(parents=True, exist_ok=True)
        self.cat_file = self.dir / "categories.json"
        self.set_file = self.dir / "settings.json"
        self.data: dict = {"active_profile": "default", "profiles": {"default": {"categories": []}}}
        self.settings: dict = dict(DEFAULT_SETTINGS)
        self.load()

    # ---------- E/S ----------
    @staticmethod
    def _bak(path: Path) -> Path:
        return path.with_suffix(path.suffix + ".bak")

    def _read(self, path: Path):
        for p in (path, self._bak(path)):
            if p.exists():
                try:
                    return json.loads(p.read_text("utf-8"))
                except (OSError, ValueError) as e:
                    logger.warning("Fichier illisible %s (%s) : essai suivant", p.name, e)
                    continue
        return None

    def _write(self, path: Path, payload) -> None:
        if path.exists():
            try:
                json.loads(path.read_text("utf-8"))  # ne sauvegarde que du JSON valide
                shutil.copy2(path, self._bak(path))
            except (OSError, ValueError):
                pass
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False), "utf-8")
        tmp.replace(path)

    def load(self) -> None:
        d = self._read(self.cat_file)
        if isinstance(d, dict) and isinstance(d.get("profiles"), dict) and d["profiles"]:
            self.data = d
            if d.get("active_profile") not in d["profiles"]:
                d["active_profile"] = next(iter(d["profiles"]))
        s = self._read(self.set_file)
        if isinstance(s, dict):
            self.settings.update(s)
        if not self.cat_file.exists():
            self.save_categories()
        if not self.set_file.exists():
            self.save_settings()

    def save_categories(self) -> None:
        self._write(self.cat_file, self.data)

    def save_settings(self) -> None:
        self._write(self.set_file, self.settings)

    def set(self, key: str, value) -> None:
        self.settings[key] = value
        self.save_settings()

    # ---------- catégories / profils ----------
    @property
    def active_profile(self) -> str:
        return self.data["active_profile"]

    def profile_names(self) -> list[str]:
        return list(self.data["profiles"])

    def categories(self) -> list[Category]:
        raw = self.data["profiles"][self.active_profile].get("categories", [])
        return sorted((Category.from_dict(c) for c in raw), key=lambda c: c.order)

    def category(self, cat_id: str) -> Category | None:
        return next((c for c in self.categories() if c.id == cat_id), None)

    def set_categories(self, cats: list[Category]) -> None:
        for i, c in enumerate(cats):
            c.order = i
        self.data["profiles"][self.active_profile]["categories"] = [c.to_dict() for c in cats]
        self.save_categories()

    def switch_profile(self, name: str) -> None:
        if name in self.data["profiles"]:
            self.data["active_profile"] = name
            self.save_categories()

    def create_profile(self, name: str, copy_active: bool = False) -> bool:
        name = name.strip()
        if not name or name in self.data["profiles"]:
            return False
        cats = [dict(c) for c in self.data["profiles"][self.active_profile]["categories"]] if copy_active else []
        self.data["profiles"][name] = {"categories": cats}
        self.data["active_profile"] = name
        self.save_categories()
        return True

    def delete_profile(self, name: str) -> bool:
        if len(self.data["profiles"]) <= 1 or name not in self.data["profiles"]:
            return False
        del self.data["profiles"][name]
        if self.data["active_profile"] == name:
            self.data["active_profile"] = next(iter(self.data["profiles"]))
        self.save_categories()
        return True
