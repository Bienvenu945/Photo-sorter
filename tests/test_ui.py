"""Tests Qt (pytest-qt) : ignorés automatiquement si PySide6/pytest-qt sont absents."""
import pytest

pytest.importorskip("PySide6")
pytest.importorskip("pytestqt")

from PIL import Image  # noqa: E402

from models import Category  # noqa: E402
from services.image_loader import ImageLoader  # noqa: E402
from widgets.category_bar import CategoryBar  # noqa: E402


def test_category_bar_is_dynamic(qtbot):
    bar = CategoryBar()
    qtbot.addWidget(bar)
    cats = [Category.new("Famille", "1"), Category.new("À vérifier", "2")]
    bar.set_categories(cats)
    with qtbot.waitSignal(bar.category_chosen) as sig:
        bar._grid.itemAt(1).widget().click()
    assert sig.args == [cats[1].id]


def test_loader_loads_in_thread_and_orients(qtbot, tmp_path):
    p = tmp_path / "big.png"
    Image.new("RGB", (4000, 1000), "red").save(p)
    loader = ImageLoader(cache_size=3)
    with qtbot.waitSignal(loader.loaded, timeout=5000) as sig:
        loader.request(p)
    img = sig.args[1]
    assert max(img.width(), img.height()) <= 2200  # thumbnail appliqué


def test_loader_reports_corrupt_file(qtbot, tmp_path):
    p = tmp_path / "bad.jpg"
    p.write_bytes(b"pas une image")
    loader = ImageLoader()
    with qtbot.waitSignal(loader.failed, timeout=5000):
        loader.request(p)
