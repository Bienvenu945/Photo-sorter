"""Tests Qt de la barre de filtres : ignorés si PySide6/pytest-qt sont absents."""
import pytest

pytest.importorskip("PySide6")
pytest.importorskip("pytestqt")

from PIL import Image  # noqa: E402

from widgets.filter_bar import FilterBar  # noqa: E402


def photos(tmp_path):
    out = {}
    for name, size in (("land1.png", (400, 300)), ("land2.png", (500, 300)), ("port1.png", (300, 450))):
        p = tmp_path / name
        Image.new("RGB", size).save(p)
        out[name] = p
    return out


def test_portrait_filter_matches_after_background_index(qtbot, tmp_path):
    files = photos(tmp_path)
    bar = FilterBar([])
    qtbot.addWidget(bar)
    bar.set_session(list(files.values()))
    with qtbot.waitSignal(bar.filterApplied, timeout=8000) as sig:
        bar.edit.set_value(":portrait")
        bar.edit.changed.emit(":portrait")
    matched, text = sig.args
    assert matched == {files["port1.png"]} and text == ":portrait"
    assert not bar.chip.isHidden() and "1 / 3" in bar.status.text()


def test_invalid_filter_shows_error_without_emitting(qtbot, tmp_path):
    bar = FilterBar([])
    qtbot.addWidget(bar)
    bar.set_session(list(photos(tmp_path).values()))
    with qtbot.assertNotEmitted(bar.filterApplied, wait=600):
        bar.edit.set_value(":portrai")
        bar.edit.changed.emit(":portrai")
    assert ":portrait" in bar.status.text()


def test_clear_removes_filter(qtbot, tmp_path):
    files = photos(tmp_path)
    bar = FilterBar([])
    qtbot.addWidget(bar)
    bar.set_session(list(files.values()))
    with qtbot.waitSignal(bar.filterApplied, timeout=8000):
        bar.edit.set_value(":paysage")
        bar.edit.changed.emit(":paysage")
    with qtbot.waitSignal(bar.filterApplied, timeout=2000) as sig:
        bar.clear()
    assert sig.args == [None, ""] and bar.chip.isHidden()


def test_recent_filters_are_remembered(qtbot, tmp_path):
    files = photos(tmp_path)
    bar = FilterBar([])
    qtbot.addWidget(bar)
    bar.set_session(list(files.values()))
    with qtbot.waitSignal(bar.recentChanged, timeout=8000) as sig:
        bar.edit.set_value(":carre")
        bar.edit.changed.emit(":carre")
    assert sig.args[0] == [":carre"]
