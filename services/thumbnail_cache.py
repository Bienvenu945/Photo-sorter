"""Cache disque de miniatures (Pillow uniquement, aucune dépendance Qt).

Fichier : ``<sha256_du_chemin>_<taille>_<octets_source>.jpg`` (qualité 85).
Fraîcheur : le mtime de la miniature est calé sur celui de la source ; si le mtime ou la
taille de la source change, la miniature est régénérée. Éviction LRU quand le cache dépasse
``max_bytes`` (date d'accès réglée explicitement, donc fiable même en ``noatime``).
"""
from __future__ import annotations

import hashlib
import logging
import os
import threading
import time
from pathlib import Path

from PIL import Image, ImageOps

logger = logging.getLogger(__name__)

THUMB_SIZES: tuple[int, ...] = (128, 192, 256, 384)
JPEG_QUALITY = 85
DEFAULT_MAX_BYTES = 500 * 1024 * 1024


class ThumbnailError(Exception):
    """Miniature impossible à générer (fichier corrompu, illisible…)."""


def default_cache_dir() -> Path:
    """~/.cache/PhotoSorterStudio/thumbs (respecte XDG_CACHE_HOME)."""
    base = os.environ.get("XDG_CACHE_HOME")
    root = Path(base) if base else Path.home() / ".cache"
    return root / "PhotoSorterStudio" / "thumbs"


class ThumbnailCache:
    """Génère, retrouve et nettoie les miniatures."""

    def __init__(self, cache_dir: Path | None = None, max_bytes: int = DEFAULT_MAX_BYTES) -> None:
        self.dir = Path(cache_dir) if cache_dir else default_cache_dir()
        self.dir.mkdir(parents=True, exist_ok=True)
        self.max_bytes = int(max_bytes)
        self._trim_lock = threading.Lock()

    # ---------- chemins ----------
    @staticmethod
    def _key(src: Path) -> str:
        return hashlib.sha256(str(Path(src).resolve()).encode("utf-8")).hexdigest()

    def thumb_path(self, src: Path, px: int) -> Path:
        """Chemin (théorique) de la miniature de ``src`` à la taille ``px``."""
        src = Path(src)
        return self.dir / f"{self._key(src)}_{px}_{src.stat().st_size}.jpg"

    def is_fresh(self, src: Path, px: int) -> bool:
        """Vrai si une miniature à jour existe déjà."""
        try:
            sst = Path(src).stat()
            tst = self.thumb_path(src, px).stat()
        except OSError:
            return False
        return tst.st_mtime_ns == sst.st_mtime_ns

    # ---------- API principale ----------
    def get(self, src: Path, px: int = 192) -> Path:
        """Retourne le chemin de la miniature (la génère si besoin)."""
        if px not in THUMB_SIZES:
            raise ValueError(f"Taille de miniature invalide : {px} (valeurs : {THUMB_SIZES})")
        src = Path(src)
        if not src.is_file():
            raise FileNotFoundError(src)
        if self.is_fresh(src, px):
            out = self.thumb_path(src, px)
            self._touch(out)
            return out
        return self._generate(src, px)

    def _touch(self, thumb: Path) -> None:
        try:
            os.utime(thumb, ns=(time.time_ns(), thumb.stat().st_mtime_ns))  # atime = maintenant
        except OSError:
            pass

    def _generate(self, src: Path, px: int) -> Path:
        final = self.thumb_path(src, px)
        key = self._key(src)
        src_mtime_ns = src.stat().st_mtime_ns
        for old in self.dir.glob(f"{key}_{px}_*.jpg"):  # versions périmées de la même source
            old.unlink(missing_ok=True)
        tmp = final.with_name(f"{final.name}.{os.getpid()}.{threading.get_ident()}.tmp")
        try:
            with Image.open(src) as im:
                im = ImageOps.exif_transpose(im)
                im.thumbnail((px, px), Image.Resampling.LANCZOS)
                if im.mode in ("RGBA", "LA", "P"):
                    rgba = im.convert("RGBA")
                    bg = Image.new("RGB", rgba.size, (255, 255, 255))
                    bg.paste(rgba, mask=rgba.getchannel("A"))
                    im = bg
                else:
                    im = im.convert("RGB")
                im.save(tmp, format="JPEG", quality=JPEG_QUALITY, optimize=True)
            os.utime(tmp, ns=(time.time_ns(), src_mtime_ns))
            tmp.replace(final)
        except Exception as e:
            tmp.unlink(missing_ok=True)
            logger.warning("Miniature impossible pour %s : %s", src.name, e)
            raise ThumbnailError(f"{src.name} : {e}") from e
        logger.debug("Miniature %dpx générée pour %s", px, src.name)
        self.trim()
        return final

    # ---------- gestion de l'espace ----------
    def _files(self) -> list[Path]:
        return [p for p in self.dir.glob("*.jpg") if p.is_file()]

    def size_bytes(self) -> int:
        """Taille totale du cache."""
        total = 0
        for p in self._files():
            try:
                total += p.stat().st_size
            except OSError:
                pass
        return total

    def trim(self) -> int:
        """Supprime les miniatures les moins récemment utilisées au-delà de max_bytes. Retourne le nombre supprimé."""
        removed = 0
        with self._trim_lock:
            entries = []
            for p in self._files():
                try:
                    st = p.stat()
                except OSError:
                    continue
                entries.append((st.st_atime_ns, st.st_size, p))
            total = sum(e[1] for e in entries)
            for _atime, size, p in sorted(entries, key=lambda e: e[0]):
                if total <= self.max_bytes:
                    break
                p.unlink(missing_ok=True)
                total -= size
                removed += 1
        if removed:
            logger.info("Cache de miniatures : %d fichier(s) supprimé(s)", removed)
        return removed

    def clear(self) -> int:
        """Vide le cache. Retourne le nombre de fichiers supprimés."""
        count = 0
        for p in self.dir.glob("*"):
            if p.is_file():
                p.unlink(missing_ok=True)
                count += 1
        return count
