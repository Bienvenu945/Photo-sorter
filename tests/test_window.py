"""Test d'intégration : tri par lot depuis la grille, un seul Ctrl+Z, filtre et historique persistant."""
import pytest

pytest.importorskip("PySide6")
pytest.importorskip("pytestqt")

from PIL import Image  # noqa: E402

from config import ConfigManager  # noqa: E402
from models import Category  # noqa: E402
from services.history_db import HistoryDB  # noqa: E402
from window import IDX_LIB, IDX_SORT, MainWindow  # noqa: E402


@pytest.fixture
def win(qtbot, tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "xdg"))
    cfg = ConfigManager(tmp_path / "cfg")
    cfg.set_categories([Category.new("Famille", "1"), Category.new("Amis", "2")])
    src = tmp_path / "src"
    src.mkdir()
    for i in range(5):
        Image.new("RGB", (400, 300), (i * 40, 80, 160)).save(src / f"p{i}.png")
    w = MainWindow(cfg, native_frame=True, history=HistoryDB(":memory:"))
    qtbot.addWidget(w)
    w.src_dir = src
    w.show()
    return w


def test_batch_sort_from_grid_then_single_undo(win, tmp_path):
    win._open_session(IDX_LIB)
    assert win.sidebar.current() == IDX_LIB and len(win.library.grid.photo_model._photos) == 5
    win.library.grid.selectAll()
    cat = win.cfg.categories()[0]
    win.sort_to(cat.id)
    assert len(list((tmp_path / "src" / "Famille").glob("*.png"))) == 5
    assert win.model.stats()["processed"] == 5 and win.library.grid.photo_model.rowCount() == 0
    assert len(win.history.last_undoable()) == 5  # UN lot
    assert win.do_undo()
    assert len(list((tmp_path / "src").glob("*.png"))) == 5 and win.model.stats()["processed"] == 0
    assert win.do_redo() and len(list((tmp_path / "src" / "Famille").glob("*.png"))) == 5


def test_batch_limit_blocks_large_selection(win, monkeypatch, tmp_path):
    from PySide6.QtWidgets import QMessageBox

    warned = []
    monkeypatch.setattr(QMessageBox, "warning", lambda *a, **k: warned.append(a))
    win.cfg.set("batch_limit", 2)
    win._open_session(IDX_LIB)
    win.library.grid.selectAll()
    win.sort_to(win.cfg.categories()[0].id)
    assert warned and not (tmp_path / "src" / "Famille").exists()


def test_single_sort_is_persistent_history(win, tmp_path):
    win._open_session(IDX_SORT)
    first = win.model.current()
    win.sort_to(win.cfg.categories()[1].id)
    assert (tmp_path / "src" / "Amis" / first.name).exists()
    assert win.history.count() == 1
    assert win.do_undo() and first.exists() and win.model.current() == first


def test_filter_restricts_sort_queue(win):
    win._open_session(IDX_SORT)
    photos = win.model.photos
    win._on_filter({photos[3]}, ":date 2026")
    assert win.model.current() == photos[3] and win.model.position() == (1, 1)
    win._on_filter(None, "")
    assert win.model.current() == photos[0] and win.model.position()[1] == 5


def test_date_sort_is_individual_in_history_and_undoable(win):
    from services.batch_ops import plan_date_sort
    from services.date_extractor import read_meta

    win._open_session(IDX_LIB)
    plan = plan_date_sort([read_meta(p) for p in win.model.photos], win.src_dir, "ym")
    win._apply_date_plan(plan)
    assert win.model.stats()["processed"] == 5 and win.history.count() == 5
    assert len(win.history.last_undoable()) == 1           # une photo à la fois
    assert win.do_undo() and win.model.stats()["processed"] == 4


def test_rename_is_one_batch_and_updates_model(win):
    from services.batch_ops import plan_rename
    from services.date_extractor import read_meta

    win._open_session(IDX_LIB)
    original = [p.name for p in win.model.photos]
    win._apply_rename_plan(plan_rename([read_meta(p) for p in win.model.photos], "{counter}"))
    assert sorted(p.name for p in win.model.photos) == [f"000{i}.png" for i in range(1, 6)]
    assert len(win.history.last_undoable()) == 5           # un seul lot
    assert win.do_undo() and [p.name for p in win.model.photos] == original
    assert win.do_redo() and win.model.photos[0].name == "0001.png"


def test_tools_can_be_disabled(win):
    win.cfg.set("date_sort", False)
    win._open_session(IDX_LIB)
    assert win._tool_ready("date_sort", "Le tri par date") is False
    assert win._tool_ready("batch_rename", "Le renommage en lot") is True
