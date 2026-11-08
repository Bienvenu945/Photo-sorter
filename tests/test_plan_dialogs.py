"""Tests Qt des fenêtres d'aperçu (tri par date, renommage) : ignorés si PySide6/pytest-qt sont absents."""
import pytest

pytest.importorskip("PySide6")
pytest.importorskip("pytestqt")

from PIL import Image  # noqa: E402

from widgets.batch_rename_dialog import BatchRenameDialog  # noqa: E402
from widgets.date_sorter_dialog import DateSorterDialog  # noqa: E402


def photos(tmp_path, n=4):
    out = []
    for i in range(n):
        p = tmp_path / f"IMG_{i}.png"
        Image.new("RGB", (200, 100)).save(p)
        out.append(p)
    return out


def test_date_sorter_preview_is_required_before_apply(qtbot, tmp_path):
    files = photos(tmp_path)
    dlg = DateSorterDialog(files, tmp_path, None, {"date_source": "mtime", "date_structure": "ym"})
    qtbot.addWidget(dlg)
    assert not dlg.b_apply.isEnabled()                     # pas d'aperçu : pas d'action possible
    qtbot.waitUntil(dlg.b_apply.isEnabled, timeout=8000)
    assert dlg.preview.count() == 4 and "4 photo(s)" in dlg.summary.text()
    assert all(f.exists() for f in files)                  # dry-run : rien n'a bougé
    assert dlg.plan == []                                  # rien n'est confirmé avant le clic
    dlg._confirm()
    assert len(dlg.plan) == 4 and dlg.choices() == {"date_source": "mtime", "date_structure": "ym"}


def test_date_sorter_changing_option_invalidates_preview(qtbot, tmp_path):
    dlg = DateSorterDialog(photos(tmp_path), tmp_path, None, {"date_source": "mtime"})
    qtbot.addWidget(dlg)
    qtbot.waitUntil(dlg.b_apply.isEnabled, timeout=8000)
    dlg.structure.set_value("ym")
    dlg.structure.changed.emit("ym")
    assert not dlg.b_apply.isEnabled()
    qtbot.waitUntil(dlg.b_apply.isEnabled, timeout=8000)


def test_rename_dialog_preview_and_invalid_template(qtbot, tmp_path):
    files = photos(tmp_path, 3)
    dlg = BatchRenameDialog(files, {"rename_template": "{counter}"})
    qtbot.addWidget(dlg)
    qtbot.waitUntil(dlg.b_apply.isEnabled, timeout=8000)
    assert dlg.preview.item(0).text().endswith("0001.png") and all(f.exists() for f in files)
    dlg.template.set_value("{nimporte}")
    dlg.template.changed.emit("{nimporte}")
    qtbot.waitUntil(lambda: "inconnue" in dlg.status.text(), timeout=8000)
    assert not dlg.b_apply.isEnabled() and dlg.preview.count() == 0
