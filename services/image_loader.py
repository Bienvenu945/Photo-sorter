"""Chargement asynchrone (QThreadPool) avec cache LRU."""
from __future__ import annotations

from collections import OrderedDict

from PIL import Image, ImageOps
from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal
from PySide6.QtGui import QImage

import models

try:  # formats avancés optionnels
    from pillow_heif import register_heif_opener
    register_heif_opener()
    models.SUPPORTED_EXTENSIONS |= {".heic", ".heif"}
except Exception:
    pass

MAX_DIM = 2200


class _Signals(QObject):
    done = Signal(str, QImage)
    failed = Signal(str, str)


class _LoadTask(QRunnable):
    def __init__(self, path: str, signals: _Signals) -> None:
        super().__init__()
        self.path, self.signals = path, signals

    def run(self) -> None:
        try:
            with Image.open(self.path) as im:
                im = ImageOps.exif_transpose(im)  # gère l'orientation EXIF
                im.thumbnail((MAX_DIM, MAX_DIM))
                im = im.convert("RGBA")
                w, h = im.size
                qimg = QImage(im.tobytes("raw", "RGBA"), w, h, 4 * w, QImage.Format.Format_RGBA8888).copy()
            self.signals.done.emit(self.path, qimg)
        except Exception as e:  # corrompue, illisible, supprimée…
            self.signals.failed.emit(self.path, f"Lecture impossible : {e}")


class ImageLoader(QObject):
    loaded = Signal(str, QImage)
    failed = Signal(str, str)

    def __init__(self, cache_size: int = 5) -> None:
        super().__init__()
        self._cache: OrderedDict[str, QImage] = OrderedDict()
        self._pending: set[str] = set()
        self._size = cache_size
        self._signals = _Signals()
        self._signals.done.connect(self._on_done)
        self._signals.failed.connect(self._on_failed)

    def request(self, path) -> None:
        key = str(path)
        if key in self._cache:
            self._cache.move_to_end(key)
            self.loaded.emit(key, self._cache[key])
        elif key not in self._pending:
            self._pending.add(key)
            QThreadPool.globalInstance().start(_LoadTask(key, self._signals))

    def prefetch(self, paths) -> None:
        for p in paths:
            if p and str(p) not in self._cache and str(p) not in self._pending:
                self.request(p)

    def _on_done(self, key: str, img: QImage) -> None:
        self._pending.discard(key)
        self._cache[key] = img
        while len(self._cache) > self._size:
            self._cache.popitem(last=False)
        self.loaded.emit(key, img)

    def _on_failed(self, key: str, msg: str) -> None:
        self._pending.discard(key)
        self.failed.emit(key, msg)

    def forget(self, path) -> None:
        self._cache.pop(str(path), None)
