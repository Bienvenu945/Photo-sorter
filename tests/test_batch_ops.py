from datetime import datetime
from pathlib import Path

import pytest

from models import PhotoSorterModel
from services import file_manager as fm
from services.batch_ops import (TemplateError, execute_plan, plan_date_sort, plan_rename, render_name, split_camera,
                                summarize, validate_template)
from services.date_extractor import PhotoMeta
from services.history_db import HistoryDB, redo_last, undo_last

DT = datetime(2026, 8, 15, 14, 32, 1)


def meta(path, date=DT, camera="Canon EOS 5D"):
    return PhotoMeta(Path(path), 1, date, date, date, "exif_original", 400, 300, camera)


def files(tmp_path, *names):
    out = []
    for n in names:
        p = tmp_path / n
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(n.encode())
        out.append(p)
    return out


def test_template_variables_and_counter():
    m = meta("/x/IMG_4821.jpg")
    assert render_name("{date}_{counter}.jpg", m, 1) == "2026-08-15_0001.jpg"
    assert render_name("{annee}-{mois}_{counter}", m, 12) == "2026-08_0012.jpg"      # extension conservée
    assert render_name("{camera}_{modele}_{jour}_{heure}", m, 1) == "Canon_EOS5D_15_14-32-01.jpg"
    assert render_name("{original}_{counter:2}.{ext}", m, 3) == "IMG_4821_03.jpg"
    assert render_name("{camera}", meta("/x/a.png", camera=None), 1) == "inconnu.png"


def test_template_validation_errors():
    for bad in ("", "  ", "{nimporte}", "a/{date}", "{date", "{date}}", "{date:3}"):
        with pytest.raises(TemplateError):
            validate_template(bad)
    validate_template("{date}_{counter:3}")


def test_names_are_sanitized():
    assert render_name("a:b?{date}.", meta("/x/p.jpg"), 1) == "a_b_2026-08-15.jpg"
    assert split_camera("Canon EOS 5D") == ("Canon", "EOS5D") and split_camera(None) == ("inconnu", "inconnu")


def test_rename_plan_is_a_dry_run(tmp_path):
    a, b = files(tmp_path, "IMG_1.jpg", "IMG_2.jpg")
    plan = plan_rename([meta(a), meta(b)], "{date}_{counter}")
    assert [op.dst.name for op in plan] == ["2026-08-15_0001.jpg", "2026-08-15_0002.jpg"]
    assert a.exists() and b.exists() and not (tmp_path / "2026-08-15_0001.jpg").exists()  # rien n'a bougé


def test_rename_conflicts_existing_and_internal(tmp_path):
    a, b, taken = files(tmp_path, "a.jpg", "b.jpg", "x.jpg")
    plan = plan_rename([meta(a), meta(b)], "x")  # les deux veulent « x.jpg », qui existe déjà
    assert [op.dst.name for op in plan] == ["x_1.jpg", "x_2.jpg"] and all(op.conflict for op in plan)


def test_rename_is_idempotent_and_never_swaps_onto_a_live_name(tmp_path):
    a, b = files(tmp_path, "2026-08-15_0001.jpg", "2026-08-15_0002.jpg")
    plan = plan_rename([meta(a), meta(b)], "{date}_{counter}")
    assert all(op.skipped for op in plan)
    c, d = files(tmp_path, "c.jpg", "d.jpg")
    swapped = plan_rename([meta(d), meta(c)], "{date}_{counter}")  # compteur inversé : cible déjà prise
    assert swapped[0].dst.name == "2026-08-15_0001_1.jpg"


def test_date_sort_plan_structures_and_skip(tmp_path):
    a, b = files(tmp_path, "a.jpg", "b.jpg")
    plan = plan_date_sort([meta(a), meta(b, datetime(2026, 9, 1))], tmp_path / "out", "ymd")
    assert plan[0].dst == tmp_path / "out" / "2026" / "08 - Août" / "2026-08-15" / "a.jpg"
    assert plan[1].dst == tmp_path / "out" / "2026" / "09 - Septembre" / "2026-09-01" / "b.jpg"
    assert plan_date_sort([meta(a)], tmp_path / "out", "ym")[0].dst == tmp_path / "out" / "2026-08" / "a.jpg"
    placed = files(tmp_path, "out/2026-08/z.jpg")[0]
    assert plan_date_sort([meta(placed)], tmp_path / "out", "ym")[0].skipped  # déjà à sa place


def test_date_sort_conflicts_inside_target(tmp_path):
    a = files(tmp_path, "s1/p.jpg")[0]
    b = files(tmp_path, "s2/p.jpg")[0]
    files(tmp_path, "out/2026-08/p.jpg")
    plan = plan_date_sort([meta(a), meta(b)], tmp_path / "out", "ym")
    assert [op.dst.name for op in plan] == ["p_1.jpg", "p_2.jpg"] and summarize(plan)["conflicts"] == 2


def test_execute_and_undo_redo_through_history(tmp_path):
    a, b = files(tmp_path, "a.jpg", "b.jpg")
    plan = plan_date_sort([meta(a), meta(b)], tmp_path / "out", "ym")
    done, errors = execute_plan(plan)
    assert not errors and (tmp_path / "out" / "2026-08" / "a.jpg").exists() and not a.exists()
    db = HistoryDB(":memory:")
    db.record_many([(op.src, dst, None, "move") for op, dst in done])  # individuelles : un Ctrl+Z chacune
    assert db.count() == 2 and len(db.last_undoable()) == 1
    undo_last(db)
    assert b.exists() and not a.exists()
    undo_last(db)
    assert a.exists()
    redo_last(db)
    assert not a.exists()


def test_rename_history_is_one_batch_and_reversible(tmp_path):
    a, b = files(tmp_path, "IMG_1.jpg", "IMG_2.jpg")
    done, _ = execute_plan(plan_rename([meta(a), meta(b)], "{counter}"))
    db = HistoryDB(":memory:")
    db.record_batch([(op.src, dst, None, "rename") for op, dst in done])
    assert len(undo_last(db)) == 2 and a.exists() and b.exists() and not (tmp_path / "0001.jpg").exists()
    assert len(redo_last(db)) == 2 and (tmp_path / "0001.jpg").exists()


def test_execute_continues_after_error(tmp_path):
    a = files(tmp_path, "a.jpg")[0]
    plan = plan_date_sort([meta(tmp_path / "absente.jpg"), meta(a)], tmp_path / "out", "ym")
    done, errors = execute_plan(plan)
    assert len(done) == 1 and len(errors) == 1 and "introuvable" in errors[0][1]


def test_move_to_renames_on_conflict_and_noop(tmp_path):
    a, b = files(tmp_path, "a.jpg", "b.jpg")
    assert fm.move_to(a, b).name == "b_1.jpg"
    assert fm.move_to(b, b) == b.resolve()


def test_model_rename_path(tmp_path):
    for n in ("a.jpg", "b.jpg"):
        (tmp_path / n).write_bytes(b"x")
    m = PhotoSorterModel()
    m.load_folder(tmp_path)
    old = m.photos[0]
    new = tmp_path / "z.jpg"
    assert m.rename_path(old, new) == 0 and m.photos[0] == new and m.index_of(new) == 0 and m.index_of(old) is None
    assert m.rename_path(tmp_path / "inconnue.jpg", new) is None
