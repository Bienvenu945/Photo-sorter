"""Affiche UNE photo : ratio conservé, centrée, chargement hors thread UI."""
from pathlib import Path

from PySide6.QtCore import QRectF, Qt, Signal
from PySide6.QtGui import QImage, QPainter, QPainterPath, QPixmap
from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout

from services.image_loader import ImageLoader


class Viewer(QFrame):
    load_failed = Signal(str, str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("Viewer")
        self.setMinimumSize(320, 240)
        self._pix: QPixmap | None = None
        self._scaled: QPixmap | None = None
        self._scaled_for = None
        self._wanted: str | None = None
        self.loader = ImageLoader(cache_size=5)
        self.loader.loaded.connect(self._on_loaded)
        self.loader.failed.connect(self._on_failed)
        self._msg = QLabel("Choisissez un dossier pour commencer")
        self._msg.setObjectName("viewerMsg")
        self._msg.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._msg.setWordWrap(True)
        lay = QVBoxLayout(self)
        lay.addWidget(self._msg)

    def show_message(self, text: str) -> None:
        self._wanted, self._pix, self._scaled = None, None, None
        self._msg.setText(text)
        self._msg.show()
        self.update()

    def show_photo(self, path: Path) -> None:
        self._wanted = str(path)
        self.loader.request(path)

    def prefetch(self, paths) -> None:
        self.loader.prefetch(paths)

    def _on_loaded(self, key: str, img: QImage) -> None:
        if key != self._wanted:
            return
        self._pix = QPixmap.fromImage(img)
        self._scaled = None
        self._msg.hide()
        self.update()

    def _on_failed(self, key: str, msg: str) -> None:
        if key == self._wanted:
            self._pix, self._scaled = None, None
            self._msg.setText("Photo illisible — passez à la suivante")
            self._msg.show()
            self.update()
        self.load_failed.emit(key, msg)

    def paintEvent(self, e) -> None:
        super().paintEvent(e)
        if not self._pix:
            return
        avail = self.rect().adjusted(12, 12, -12, -12).size()
        # petites photos : agrandissement limité à x2 ; grandes : réduction
        cap = self._pix.size() * 2
        target = avail.boundedTo(cap)
        key = (target.width(), target.height(), self._pix.cacheKey())
        if self._scaled is None or self._scaled_for != key:
            self._scaled = self._pix.scaled(target, Qt.AspectRatioMode.KeepAspectRatio,
                                            Qt.TransformationMode.SmoothTransformation)
            self._scaled_for = key
        w, h = self._scaled.width(), self._scaled.height()
        x, y = (self.width() - w) / 2, (self.height() - h) / 2
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        path = QPainterPath()
        path.addRoundedRect(QRectF(x, y, w, h), 12, 12)
        p.setClipPath(path)
        p.drawPixmap(int(x), int(y), self._scaled)
