"""Date de prise de vue et métadonnées légères (Pillow uniquement, lecture seule)."""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from PIL import Image

logger = logging.getLogger(__name__)

EXIF_IFD = 0x8769
TAG_DATETIME_ORIGINAL, TAG_DATETIME_DIGITIZED, TAG_DATETIME = 0x9003, 0x9004, 0x0132
TAG_MAKE, TAG_MODEL, TAG_ORIENTATION = 0x010F, 0x0110, 0x0112

MONTHS_FR = ["Janvier", "Février", "Mars", "Avril", "Mai", "Juin", "Juillet", "Août", "Septembre",
             "Octobre", "Novembre", "Décembre"]
PREFERENCES = ("exif", "mtime", "filename")
SQUARE_TOLERANCE = 0.05

_FILENAME_RE = re.compile(
    r"(?<!\d)((?:19|20)\d{2})[-_.]?(0[1-9]|1[0-2])[-_.]?(0[1-9]|[12]\d|3[01])"
    r"(?:(?:[-_ T.]?([01]\d|2[0-3])([0-5]\d)([0-5]\d))|(?!\d))")


@dataclass(frozen=True)
class ExtractedDate:
    value: datetime
    source: str  # exif_original | exif_digitized | exif_datetime | filename | mtime | ctime


@dataclass(frozen=True)
class PhotoMeta:
    path: Path
    size_bytes: int
    mtime: datetime
    added: datetime          # ctime : approximation de « ajouté à ce dossier »
    date: datetime
    date_source: str
    width: int = 0
    height: int = 0
    camera: str | None = None

    @property
    def orientation(self) -> str:
        """'portrait', 'paysage', 'carre' ou 'inconnu' (dimensions illisibles)."""
        if self.width <= 0 or self.height <= 0:
            return "inconnu"
        if abs(self.width - self.height) / max(self.width, self.height) <= SQUARE_TOLERANCE:
            return "carre"
        return "paysage" if self.width > self.height else "portrait"


def parse_exif_datetime(value: object) -> datetime | None:
    """'2026:08:15 14:32:01' -> datetime ; None si absent ou invalide (ex. 0000:00:00)."""
    if isinstance(value, bytes):
        value = value.decode("ascii", "ignore")
    if not isinstance(value, str):
        return None
    text = value.strip().rstrip("\x00")
    for fmt in ("%Y:%m:%d %H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y:%m:%d"):
        try:
            return datetime.strptime(text[:19] if "%H" in fmt else text[:10], fmt)
        except ValueError:
            continue
    return None


def date_from_filename(name: str) -> datetime | None:
    """Parse IMG_20260815_143201.jpg, 2026-08-15 10.30.jpg, PXL_20260815… (années 1990-2099)."""
    for m in _FILENAME_RE.finditer(name):
        y, mo, d, hh, mi, ss = m.groups()
        try:
            return datetime(int(y), int(mo), int(d), int(hh or 0), int(mi or 0), int(ss or 0))
        except ValueError:
            continue
    return None


def _exif_dates(exif) -> list[tuple[str, datetime]]:
    sub = {}
    try:
        sub = exif.get_ifd(EXIF_IFD)
    except Exception:  # IFD corrompu
        pass
    found = []
    for label, tag, src in (("exif_original", TAG_DATETIME_ORIGINAL, sub), ("exif_digitized", TAG_DATETIME_DIGITIZED, sub),
                            ("exif_datetime", TAG_DATETIME, exif)):
        dt = parse_exif_datetime(src.get(tag)) or (parse_exif_datetime(exif.get(tag)) if src is sub else None)
        if dt:
            found.append((label, dt))
    return found


def _read_exif(path: Path):
    try:
        with Image.open(path) as im:
            return im.getexif(), im.size
    except Exception as e:
        logger.debug("EXIF illisible pour %s : %s", path.name, e)
        return None, (0, 0)


def _file_dates(path: Path) -> tuple[ExtractedDate, ExtractedDate]:
    st = path.stat()
    return (ExtractedDate(datetime.fromtimestamp(st.st_mtime), "mtime"),
            ExtractedDate(datetime.fromtimestamp(st.st_ctime), "ctime"))


def _resolve(path: Path, exif, preference: str) -> ExtractedDate:
    mtime, ctime = _file_dates(path)
    exif_found = [ExtractedDate(dt, label) for label, dt in _exif_dates(exif)] if exif is not None else []
    if preference == "mtime":
        chain = [mtime, ctime]
    elif preference == "filename":
        fn = date_from_filename(path.name)
        chain = ([ExtractedDate(fn, "filename")] if fn else []) + exif_found + [mtime, ctime]
    else:
        chain = exif_found + [mtime, ctime]
    return chain[0]


def extract_date(path: Path, preference: str = "exif") -> ExtractedDate:
    """Date d'une photo. Priorité « exif » : DateTimeOriginal > Digitized > DateTime > mtime > ctime."""
    if preference not in PREFERENCES:
        raise ValueError(f"Source de date inconnue : {preference!r} (valeurs : {PREFERENCES})")
    path = Path(path)
    exif = _read_exif(path)[0] if preference != "mtime" else None
    return _resolve(path, exif, preference)


def read_meta(path: Path, date_preference: str = "exif") -> PhotoMeta:
    """Métadonnées utiles au tri et aux filtres, avec une seule ouverture du fichier. Ne lève pas sur image corrompue."""
    path = Path(path)
    st = path.stat()
    exif, (w, h) = _read_exif(path)
    camera = None
    if exif is not None:
        orient = exif.get(TAG_ORIENTATION)
        if orient in (5, 6, 7, 8):
            w, h = h, w
        make, model = str(exif.get(TAG_MAKE) or "").strip("\x00 "), str(exif.get(TAG_MODEL) or "").strip("\x00 ")
        camera = (model if model.lower().startswith(make.lower()) else f"{make} {model}").strip() or None
    d = _resolve(path, exif, date_preference)
    return PhotoMeta(path, st.st_size, datetime.fromtimestamp(st.st_mtime), datetime.fromtimestamp(st.st_ctime),
                     d.value, d.source, w, h, camera)


def date_folder(dt: datetime, structure: str = "ymd") -> Path:
    """Dossier relatif (indépendant de la locale). 'ymd' : 2026/08 - Août/2026-08-15 ; 'ym' : 2026-08."""
    if structure == "ym":
        return Path(f"{dt.year}-{dt.month:02d}")
    if structure == "ymd":
        return Path(f"{dt.year}") / f"{dt.month:02d} - {MONTHS_FR[dt.month - 1]}" / f"{dt.year}-{dt.month:02d}-{dt.day:02d}"
    raise ValueError(f"Structure inconnue : {structure!r} (valeurs : 'ymd', 'ym')")
