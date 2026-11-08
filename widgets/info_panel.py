"""Zone D : panneau d'informations contextuelles (lecture des métadonnées hors du thread UI)."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal
from PySide6.QtWidgets import QLabel, QWidget

from services.date_extractor import PhotoMeta, read_meta
from widgets.glass import GlassCard

_SOURCES = {"exif_original": "date de prise de vue", "exif_digitized": "date de numérisation",
            "exif_datetime": "date EXIF", "filename": "date du nom de fichier",
            "mtime": "date de modification", "ctime": "date de création"}


def human_size(n: int) -> str:
    """12345678 -> '11,8 Mo'."""
    value = float(n)
    for unit in ("o", "Ko", "Mo", "Go"):
        if value < 1024 or unit == "Go":
            return f"{int(value)} {unit}" if unit == "o" else f"{value:.1f} {unit}".replace(".", ",")
        value /= 1024
    return f"{n} o"


class _Signals(QObject):
    done = Signal(str, object)  # chemin, PhotoMeta | None


class _MetaTask(QRunnable):
    def __init__(self, path: str, signals: _Signals) -> None:
        super().__init__()
        self.path, self.signals = path, signals

    def run(self) -> None:
        try:
            meta = read_meta(Path(self.path))
        except Exception:  # fichier disparu, illisible…
            meta = None
        self.signals.done.emit(self.path, meta)


class InfoPanel(GlassCard):
    FIELDS = (("name", "Nom"), ("dims", "Dimensions"), ("format", "Format"), ("size", "Taille"),
              ("date", "Date"), ("camera", "Appareil"), ("folder", "Dossier"))

    def __init__(self, parent=None) -> None:
        super().__init__("Informations", parent=parent, radius=18.0)
        self.setFixedWidth(272)
        self._wanted: str | None = None
        self._signals = _Signals()
        self._signals.done.connect(self._on_meta)
        self._values: dict[str, QLabel] = {}
        for key, caption in self.FIELDS:
            cap = QLabel(caption)
            cap.setObjectName("muted")
            val = QLabel("—")
            val.setWordWrap(True)
            val.setContentsMargins(0, 0, 0, 10)
            self._values[key] = val
            self.add_widget(cap)
            self.add_widget(val)
        spacer = QWidget()
        self.add_widget(spacer, 1)

    def show_photo(self, path: Path | None) -> None:
        """Affiche une photo (ou vide le panneau si ``path`` est None)."""
        if path is None:
            self._wanted = None
            for v in self._values.values():
                v.setText("—")
            return
        self._wanted = str(path)
        self._values["name"].setText(path.name)
        self._values["format"].setText(path.suffix.lstrip(".").upper() or "—")
        self._values["folder"].setText(str(path.parent))
        for k in ("dims", "size", "date", "camera"):
            self._values[k].setText("…")
        QThreadPool.globalInstance().start(_MetaTask(str(path), self._signals))

    def _on_meta(self, key: str, meta: PhotoMeta | None) -> None:
        if key != self._wanted:
            return  # réponse périmée
        if meta is None:
            for k in ("dims", "size", "date", "camera"):
                self._values[k].setText("—")
            return
        self._values["dims"].setText(f"{meta.width} × {meta.height}" if meta.width else "—")
        self._values["size"].setText(human_size(meta.size_bytes))
        self._values["date"].setText(f"{meta.date:%d/%m/%Y %H:%M}\n({_SOURCES.get(meta.date_source, '')})")
        self._values["camera"].setText(meta.camera or "—")
