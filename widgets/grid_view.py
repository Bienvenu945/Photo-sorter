"""Grille de miniatures : QListView + modèle virtuel (chargement paresseux), colonnes configurables."""
from __future__ import annotations

import re
from collections import OrderedDict
from pathlib import Path

from PySide6.QtCore import (QAbstractListModel, QModelIndex, QObject, QRect, QRectF, QRunnable, QSize, Qt,
                            QThreadPool, Signal)
from PySide6.QtGui import QFontMetrics, QImage, QPainter, QPainterPath, QPixmap
from PySide6.QtWidgets import QAbstractItemView, QListView, QStyle, QStyledItemDelegate

import theme
from services.thumbnail_cache import THUMB_SIZES, ThumbnailCache

PIXMAP_CACHE_MAX = 800


def natural_key(p: Path):
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", p.name)]


# ---------------------------------------------------------------- miniatures asynchrones
class _ThumbSignals(QObject):
    ready = Signal(int, str, QImage)


class _ThumbTask(QRunnable):
    def __init__(self, gen: int, path: str, px: int, cache: ThumbnailCache, signals: _ThumbSignals) -> None:
        super().__init__()
        self.gen, self.path, self.px, self.cache, self.signals = gen, path, px, cache, signals

    def run(self) -> None:
        try:
            img = QImage(str(self.cache.get(Path(self.path), self.px)))  # lecture disque : hors thread UI
        except Exception:
            img = QImage()
        self.signals.ready.emit(self.gen, self.path, img)


class PhotoListModel(QAbstractListModel):
    """Modèle virtuel : une miniature n'est demandée que lorsque la vue l'affiche."""

    def __init__(self, cache: ThumbnailCache, px: int = 192) -> None:
        super().__init__()
        self._cache, self._px, self._gen, self._prio = cache, px, 0, 0
        self._photos: list[Path] = []
        self._rows: dict[str, int] = {}
        self._pix: OrderedDict[str, QPixmap] = OrderedDict()
        self._pending: set[str] = set()
        self._failed: set[str] = set()
        self._pool = QThreadPool()
        self._pool.setMaxThreadCount(3)
        self._signals = _ThumbSignals()
        self._signals.ready.connect(self._on_ready)

    def rowCount(self, parent=QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self._photos)

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or not 0 <= index.row() < len(self._photos):
            return None
        path = self._photos[index.row()]
        if role == Qt.ItemDataRole.DisplayRole:
            return path.name
        if role == Qt.ItemDataRole.ToolTipRole:
            return str(path)
        if role == Qt.ItemDataRole.UserRole:
            return path
        if role == Qt.ItemDataRole.DecorationRole:
            key = str(path)
            pm = self._pix.get(key)
            if pm is not None:
                self._pix.move_to_end(key)
                return pm
            if key not in self._pending and key not in self._failed:
                self._pending.add(key)
                self._prio += 1  # les plus récemment affichées d'abord
                self._pool.start(_ThumbTask(self._gen, key, self._px, self._cache, self._signals), self._prio)
        return None

    def set_photos(self, photos: list[Path]) -> None:
        self._pool.clear()
        self._pending.clear()
        self.beginResetModel()
        self._photos = list(photos)
        self._rows = {str(p): i for i, p in enumerate(self._photos)}
        self.endResetModel()

    def set_px(self, px: int) -> None:
        self._px, self._gen = px, self._gen + 1
        self._pool.clear()
        self._pending.clear()
        self._failed.clear()
        self._pix.clear()
        if self._photos:
            self.dataChanged.emit(self.index(0), self.index(len(self._photos) - 1),
                                  [Qt.ItemDataRole.DecorationRole])

    def _on_ready(self, gen: int, key: str, img: QImage) -> None:
        if gen != self._gen:
            return
        self._pending.discard(key)
        if img.isNull():
            self._failed.add(key)
            return
        self._pix[key] = QPixmap.fromImage(img)
        while len(self._pix) > PIXMAP_CACHE_MAX:
            self._pix.popitem(last=False)
        row = self._rows.get(key)
        if row is not None:
            idx = self.index(row)
            self.dataChanged.emit(idx, idx, [Qt.ItemDataRole.DecorationRole])


class PhotoDelegate(QStyledItemDelegate):
    def __init__(self, view: QListView) -> None:
        super().__init__(view)
        self.view, self.px, self.list_mode = view, 192, False

    cell = 0  # taille d'une case en mode colonnes fixes (0 = déduite de la taille des miniatures)

    def sizeHint(self, option, index) -> QSize:
        if self.list_mode:
            return QSize(max(320, self.view.viewport().width() - 24), 64)
        side = self.cell or self.px + 16
        return QSize(side, side)

    def paint(self, painter: QPainter, option, index) -> None:
        pal = theme.current()
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        selected = bool(option.state & QStyle.StateFlag.State_Selected)
        hover = bool(option.state & QStyle.StateFlag.State_MouseOver)
        card = QRectF(option.rect).adjusted(4, 4, -4, -4)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(theme.qcolor(pal.accent_a, 0.22) if selected else theme.ov(26 if hover else 12))
        painter.drawRoundedRect(card, 12, 12)
        pm = index.data(Qt.ItemDataRole.DecorationRole)
        area = card.adjusted(6, 6, -6, -6)
        if self.list_mode:
            area = QRectF(card.left() + 6, card.top() + 6, card.height() - 12, card.height() - 12)
        if pm is not None and not pm.isNull():
            size = pm.size().scaled(int(area.width()), int(area.height()), Qt.AspectRatioMode.KeepAspectRatio)
            target = QRectF(area.center().x() - size.width() / 2, area.center().y() - size.height() / 2,
                            size.width(), size.height())
            clip = QPainterPath()
            clip.addRoundedRect(target, 8, 8)
            painter.setClipPath(clip)
            painter.drawPixmap(target.toRect(), pm)
            painter.setClipping(False)
        else:  # squelette en attendant la miniature
            painter.setBrush(theme.ov(18))
            painter.drawRoundedRect(area.adjusted(4, 4, -4, -4), 8, 8)
        if self.list_mode:
            fm = QFontMetrics(option.font)
            text = fm.elidedText(index.data(Qt.ItemDataRole.DisplayRole) or "", Qt.TextElideMode.ElideMiddle,
                                 int(card.width() - area.width() - 32))
            painter.setPen(theme.fg())
            painter.drawText(QRect(int(area.right() + 14), int(card.top()), int(card.width() - area.width() - 28),
                                   int(card.height())), Qt.AlignmentFlag.AlignVCenter, text)
        if selected:
            painter.setClipping(False)
            painter.setPen(theme.qcolor(pal.accent_a, 0.95))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(card, 12, 12)
        painter.restore()




class GridView(QListView):
    """Grille (ou liste) avec sélection multiple (Ctrl/Maj + clic, Ctrl+A) et colonnes fixes ou automatiques."""

    openRequested = Signal(object)    # Path (double-clic)
    selectedPaths = Signal(object)    # list[Path] (ne pas nommer « selectionChanged » : méthode virtuelle de Qt)

    def __init__(self, cache: ThumbnailCache, px: int = 192, columns: int = 4, parent=None) -> None:
        super().__init__(parent)
        self._columns = columns
        self.photo_model = PhotoListModel(cache, px if px in THUMB_SIZES else 192)
        self.setModel(self.photo_model)
        self.delegate = PhotoDelegate(self)
        self.delegate.px = self.photo_model._px
        self.setItemDelegate(self.delegate)
        self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.setMovement(QListView.Movement.Static)
        self.setResizeMode(QListView.ResizeMode.Adjust)
        self.setUniformItemSizes(True)
        self.setMouseTracking(True)
        self.setFrameShape(QListView.Shape.NoFrame)
        self.setStyleSheet("QListView { background: transparent; border: none; outline: 0; }")
        self.viewport().setAutoFillBackground(False)
        self.doubleClicked.connect(lambda idx: self.openRequested.emit(idx.data(Qt.ItemDataRole.UserRole)))
        self.selectionModel().selectionChanged.connect(lambda *_: self.selectedPaths.emit(self.selected()))
        self.set_mode("grid")

    # ----- API -----
    def set_photos(self, photos: list[Path]) -> None:
        self.photo_model.set_photos(photos)

    def selected(self) -> list[Path]:
        rows = sorted(i.row() for i in self.selectionModel().selectedIndexes())
        return [self.photo_model._photos[r] for r in rows]

    def current_path(self) -> Path | None:
        idx = self.currentIndex()
        return idx.data(Qt.ItemDataRole.UserRole) if idx.isValid() else None

    def set_mode(self, mode: str) -> None:
        listing = mode == "list"
        self.delegate.list_mode = listing
        if listing:
            self.setViewMode(QListView.ViewMode.ListMode)
            self.setGridSize(QSize())
            self.setSpacing(2)
        else:
            self.setViewMode(QListView.ViewMode.IconMode)
            self.setSpacing(0)
        self.setWrapping(not listing)
        self._relayout()

    def set_columns(self, columns: int) -> None:
        """0 = automatique (selon la taille des miniatures), sinon nombre de colonnes fixe."""
        self._columns = columns
        self._relayout()

    def set_thumb_px(self, px: int) -> None:
        if px in THUMB_SIZES:
            self.delegate.px = px
            self.photo_model.set_px(px)
            self._relayout()

    @property
    def columns(self) -> int:
        return self._columns

    # ----- mise en page -----
    def cell_side(self) -> int:
        if self._columns <= 0:
            return self.delegate.px + 16
        return max(96, (self.viewport().width() - 20) // self._columns)

    def _relayout(self) -> None:
        if self.delegate.list_mode:
            self.doItemsLayout()
            return
        side = self.cell_side()
        self.delegate.cell = side if self._columns > 0 else 0
        self.setGridSize(QSize(side, side))
        if self._columns > 0:  # colonnes fixes : la résolution suit la taille de la case
            wanted = next((s for s in THUMB_SIZES if s >= side - 16), THUMB_SIZES[-1])
            if wanted != self.photo_model._px:
                self.delegate.px = wanted
                self.photo_model.set_px(wanted)
        self.doItemsLayout()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if self._columns > 0 and not self.delegate.list_mode:
            self._relayout()
