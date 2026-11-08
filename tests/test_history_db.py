import pytest

from services import file_manager as fm
from services.history_db import HistoryDB, redo_last, undo_last


def mk(tmp_path, name, data=b"x"):
    p = tmp_path / "src" / name
    p.parent.mkdir(exist_ok=True)
    p.write_bytes(data)
    return p


def sort_one(db, tmp_path, name, cat="A", mode="move", batch=None):
    src = mk(tmp_path, name)
    dst = fm.transfer(src, tmp_path / cat, mode)
    db.record(src, dst, cat, mode, batch)
    return src, dst


def test_persistence_across_reopen(tmp_path):
    path = tmp_path / "h.db"
    db = HistoryDB(path)
    src, dst = sort_one(db, tmp_path, "a.jpg")
    db.close()
    db2 = HistoryDB(path)
    assert db2.count() == 1
    assert undo_last(db2)[0].src == src and src.exists() and not dst.exists()


def test_undo_redo_single(tmp_path):
    db = HistoryDB(":memory:")
    src, dst = sort_one(db, tmp_path, "a.jpg")
    assert len(undo_last(db)) == 1 and src.exists()
    assert undo_last(db) == []  # plus rien à annuler
    assert len(redo_last(db)) == 1 and dst.exists() and not src.exists()
    assert redo_last(db) == []


def test_lifo_undo_order(tmp_path):
    db = HistoryDB(":memory:")
    s1, d1 = sort_one(db, tmp_path, "a.jpg")
    s2, d2 = sort_one(db, tmp_path, "b.jpg")
    undo_last(db)
    assert s2.exists() and not s1.exists()
    undo_last(db)
    assert s1.exists()
    redo_last(db)  # rétablit a.jpg d'abord (dernier annulé)
    assert d1.exists() and s2.exists()


def test_batch_is_one_undo(tmp_path):
    db = HistoryDB(":memory:")
    items = []
    for n in ("a.jpg", "b.jpg", "c.jpg"):
        src = mk(tmp_path, n)
        items.append((src, fm.transfer(src, tmp_path / "Lot"), "Lot", "move"))
    db.record_batch(items)
    assert len(undo_last(db)) == 3
    assert all(s.exists() for s, *_ in items)
    assert len(redo_last(db)) == 3
    assert all(d.exists() for _, d, *_ in items)


def test_new_operation_clears_redo(tmp_path):
    db = HistoryDB(":memory:")
    sort_one(db, tmp_path, "a.jpg")
    undo_last(db)
    sort_one(db, tmp_path, "b.jpg")
    assert db.last_redoable() == []


def test_limit_prunes_oldest(tmp_path):
    db = HistoryDB(":memory:", limit=3)
    for i in range(6):
        db.record(tmp_path / f"s{i}", tmp_path / f"d{i}", "A", "move")
    assert db.count() == 3
    assert [e.src.name for e in db.entries()] == ["s5", "s4", "s3"]


def test_blocked_when_file_moved_by_hand(tmp_path):
    db = HistoryDB(":memory:")
    src, dst = sort_one(db, tmp_path, "a.jpg")
    dst.unlink()
    with pytest.raises(fm.FileOperationError):
        undo_last(db)
    assert len(db.last_undoable()) == 1  # rien marqué comme annulé


def test_copy_and_rename_modes(tmp_path):
    db = HistoryDB(":memory:")
    src, dst = sort_one(db, tmp_path, "c.jpg", mode="copy")
    undo_last(db)
    assert src.exists() and not dst.exists()  # copie supprimée, original intact
    redo_last(db)
    assert src.exists() and dst.exists()
    a = mk(tmp_path, "old.jpg")
    b = a.with_name("new.jpg")
    a.rename(b)
    db.record(a, b, None, "rename")
    undo_last(db)
    assert a.exists() and not b.exists()


def test_redo_renames_on_conflict_and_updates_db(tmp_path):
    db = HistoryDB(":memory:")
    src, dst = sort_one(db, tmp_path, "a.jpg")
    undo_last(db)
    dst.write_bytes(b"autre fichier")  # le nom de destination est pris entre-temps
    (done,) = redo_last(db)
    assert done.dst.name == "a_1.jpg" and done.dst.exists()
    assert db.entries()[0].dst.name == "a_1.jpg"


def test_undo_reports_restored_path(tmp_path):
    db = HistoryDB(":memory:")
    src, dst = sort_one(db, tmp_path, "a.jpg")
    mk(tmp_path, "a.jpg")  # le nom d'origine est repris entre-temps
    (entry,) = undo_last(db)
    assert entry.restored.name == "a_1.jpg" and entry.restored.exists()
