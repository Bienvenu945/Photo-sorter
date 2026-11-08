"""Tests Qt (pytest-qt) du modèle de la bibliothèque : ignorés si PySide6/pytest-qt sont absents."""
import pytest

pytest.importorskip("PySide6")
pytest.importorskip("pytestqt")

from PIL import Image  # noqa: E402
from PySide6.QtCore import Qt  # noqa: E402

from services.thumbnail_cache import ThumbnailCache  # noqa: E402
from widgets.grid_view import PhotoListModel, natural_key  # noqa: E402


def make_photos(tmp_path, n=3):
    paths = []
    for i in range(n):
        p = tmp_path / f"img{n - i}.png"
        Image.new("RGB", (600, 400), (i * 60, 100, 200)).save(p)
        paths.append(p)
    return paths


def test_natural_sort_key(tmp_path):
    names = [p.name for p in sorted(make_photos(tmp_path, 12), key=natural_key)]
    assert names[:3] == ["img1.png", "img2.png", "img3.png"] and names[-1] == "img12.png"


def test_model_loads_thumbnails_lazily(qtbot, tmp_path):
    photos = make_photos(tmp_path)
    model = PhotoListModel(ThumbnailCache(tmp_path / "cache"), 128)
    model.set_photos(photos)
    assert model.rowCount() == 3
    assert model.data(model.index(0), Qt.ItemDataRole.DecorationRole) is None  # pas encore chargée
    with qtbot.waitSignal(model.dataChanged, timeout=5000):
        pass
    pm = model.data(model.index(0), Qt.ItemDataRole.DecorationRole)
    assert pm is not None and max(pm.width(), pm.height()) == 128
    assert model.data(model.index(0), Qt.ItemDataRole.UserRole) == photos[0]


def test_corrupt_file_is_marked_failed(qtbot, tmp_path):
    bad = tmp_path / "bad.jpg"
    bad.write_bytes(b"x")
    model = PhotoListModel(ThumbnailCache(tmp_path / "cache"), 128)
    model.set_photos([bad])
    model.data(model.index(0), Qt.ItemDataRole.DecorationRole)
    qtbot.waitUntil(lambda: str(bad) in model._failed, timeout=5000)
