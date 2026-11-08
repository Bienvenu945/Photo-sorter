from models import PhotoSorterModel


def setup(tmp_path, n=3):
    for i in range(n):
        (tmp_path / f"p{i + 1}.jpg").write_bytes(b"x")
    (tmp_path / "notes.txt").write_text("x")
    (tmp_path / "Famille").mkdir()
    (tmp_path / "Famille" / "old.jpg").write_bytes(b"x")
    m = PhotoSorterModel()
    m.load_folder(tmp_path)
    return m


def test_load_ignores_non_images_and_subdirs(tmp_path):
    m = setup(tmp_path)
    assert m.total == 3 and m.ignored == 1


def test_exclude_category_dirs_when_recursive(tmp_path):
    setup(tmp_path)
    m = PhotoSorterModel()
    assert m.load_folder(tmp_path, ["Famille"], include_subdirs=True) == 3
    assert m.load_folder(tmp_path, [], include_subdirs=True) == 4


def test_natural_order(tmp_path):
    for n in (10, 2, 1):
        (tmp_path / f"img{n}.png").write_bytes(b"x")
    m = PhotoSorterModel()
    m.load_folder(tmp_path)
    assert [p.name for p in m.photos] == ["img1.png", "img2.png", "img10.png"]


def test_register_skip_undo(tmp_path):
    m = setup(tmp_path)
    m.register(m.current(), tmp_path / "x", "c1", "move")
    assert m.position() == (2, 3) and m.stats()["processed"] == 1
    m.skip()
    assert m.previous() is False or m.current() is not None
    m.undo_last()
    assert m.index == 0 and m.stats()["processed"] == 0


def test_finish(tmp_path):
    m = setup(tmp_path, 2)
    for _ in range(2):
        m.register(m.current(), tmp_path / "x", "c", "move")
    assert m.finished() and m.stats()["remaining"] == 0


def test_filter_scopes_queue_and_progress(tmp_path):
    m = setup(tmp_path, 5)
    assert m.set_allowed([m.photos[1], m.photos[3]]) == 2
    assert m.current() == m.photos[1] and m.position() == (1, 2)
    m.skip()
    assert m.current() == m.photos[3] and m.position() == (2, 2)
    m.skip()
    assert m.finished() and m.stats()["scope_total"] == 2
    m.set_allowed(None)  # retirer le filtre
    assert m.current() == m.photos[0] and m.position() == (1, 5)


def test_filter_progress_and_remaining(tmp_path):
    m = setup(tmp_path, 4)
    m.set_allowed([m.photos[0], m.photos[2]])
    m.register(m.current(), tmp_path / "x", "c", "move")
    st = m.stats()
    assert st["remaining"] == 1 and st["scope_done"] == 1 and st["scope_total"] == 2 and st["total"] == 4
    assert m.set_allowed([]) == 0 and m.stats()["remaining"] == 0


def test_register_at_restore_reapply(tmp_path):
    m = setup(tmp_path, 4)
    m.register_at(2, tmp_path / "x", "c", "move")
    assert 2 in m.done and m.index == 0 and m.counts["c"] == 1
    assert m.restore(m.photos[2], "c") == 2 and 2 not in m.done and m.counts["c"] == 0
    assert m.reapply(m.photos[2], "c") == 2 and 2 in m.done
    assert m.restore(tmp_path / "inconnue.jpg", "c") is None


def test_restore_with_renamed_path(tmp_path):
    m = setup(tmp_path, 3)
    old = m.photos[1]
    m.register_at(1, tmp_path / "x", "c", "move")
    new = tmp_path / "p2_1.jpg"
    assert m.restore(old, "c", new) == 1 and m.photos[1] == new and m.index_of(new) == 1 and m.index_of(old) is None


def test_go_to_refuses_done_and_filtered(tmp_path):
    m = setup(tmp_path, 3)
    m.register_at(1, tmp_path / "x", "c", "move")
    assert not m.go_to(1) and m.go_to(2) and m.index == 2
    m.set_allowed([m.photos[0]])
    assert not m.go_to(2)
