"""Tests Qt (pytest-qt) de la grille : ignorés si PySide6/pytest-qt sont absents."""
import pytest

pytest.importorskip("PySide6")
pytest.importorskip("pytestqt")

from PIL import Image  # noqa: E402

from services.thumbnail_cache import ThumbnailCache  # noqa: E402
from widgets.grid_view import GridView  # noqa: E402


def make_photos(tmp_path, n=6):
    out = []
    for i in range(n):
        p = tmp_path / f"p{i}.png"
        Image.new("RGB", (400, 300), (i * 30, 90, 160)).save(p)
        out.append(p)
    return out


def make_view(qtbot, tmp_path, columns=4):
    view = GridView(ThumbnailCache(tmp_path / "cache"), 192, columns)
    qtbot.addWidget(view)
    view.resize(860, 600)
    view.show()
    qtbot.waitExposed(view)
    return view


def test_fixed_columns_define_cell_size(qtbot, tmp_path):
    view = make_view(qtbot, tmp_path, 4)
    assert view.cell_side() == max(96, (view.viewport().width() - 20) // 4)
    view.set_columns(0)  # automatique : suit la taille des miniatures
    assert view.cell_side() == view.delegate.px + 16


def test_thumbnail_resolution_follows_cell(qtbot, tmp_path):
    view = make_view(qtbot, tmp_path, 3)
    assert view.photo_model._px >= view.cell_side() - 16 or view.photo_model._px == 384


def test_multi_selection_and_signal(qtbot, tmp_path):
    photos = make_photos(tmp_path)
    view = make_view(qtbot, tmp_path)
    view.set_photos(photos)
    with qtbot.waitSignal(view.selectedPaths, timeout=2000) as sig:
        view.selectAll()
    assert view.selected() == photos and len(sig.args[0]) == 6
    view.clearSelection()
    assert view.selected() == []


def test_list_mode_switch(qtbot, tmp_path):
    view = make_view(qtbot, tmp_path)
    view.set_mode("list")
    assert view.delegate.list_mode
    view.set_mode("grid")
    assert not view.delegate.list_mode
