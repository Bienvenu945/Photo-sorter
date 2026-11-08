import pytest

from models import SortOperation
from services import file_manager as fm


def mk(tmp_path, name="photo.jpg", data=b"x"):
    p = tmp_path / "src" / name
    p.parent.mkdir(exist_ok=True)
    p.write_bytes(data)
    return p


def test_move_and_undo(tmp_path):
    src = mk(tmp_path)
    dst = fm.transfer(src, tmp_path / "Famille")
    assert dst.exists() and not src.exists()
    op = SortOperation(src, dst, "c", 0.0, "move")
    assert fm.undo(op) == src and src.exists()


def test_copy_and_undo(tmp_path):
    src = mk(tmp_path)
    dst = fm.transfer(src, tmp_path / "A", mode="copy")
    assert src.exists() and dst.exists()
    fm.undo(SortOperation(src, dst, "c", 0.0, "copy"))
    assert src.exists() and not dst.exists()


def test_duplicates(tmp_path):
    out = tmp_path / "A"
    names = []
    for _ in range(3):
        names.append(fm.transfer(mk(tmp_path), out).name)
    assert names == ["photo.jpg", "photo_1.jpg", "photo_2.jpg"]
    assert fm.transfer(mk(tmp_path), out, policy="skip") is None
    assert fm.transfer(mk(tmp_path, data=b"new"), out, policy="replace").read_bytes() == b"new"


def test_errors(tmp_path):
    with pytest.raises(fm.FileOperationError):
        fm.transfer(tmp_path / "nope.jpg", tmp_path / "A")
    with pytest.raises(fm.FileOperationError):
        fm.undo(SortOperation(tmp_path / "a", tmp_path / "gone", "c", 0.0, "move"))


def test_safe_name():
    assert fm.safe_folder_name('a/b:c') == "a_b_c"


def test_multi_level_undo_lifo(tmp_path):
    ops = []
    for n in ("a.jpg", "b.jpg", "c.jpg"):
        src = mk(tmp_path, n)
        ops.append(SortOperation(src, fm.transfer(src, tmp_path / "A"), "c", 0.0, "move"))
    for op in reversed(ops):
        fm.undo(op)
        assert op.src.exists()


def test_undo_when_origin_name_taken(tmp_path):
    src = mk(tmp_path)
    dst = fm.transfer(src, tmp_path / "A")
    mk(tmp_path)  # un nouveau fichier occupe le nom d'origine
    restored = fm.undo(SortOperation(src, dst, "c", 0.0, "move"))
    assert restored.name == "photo_1.jpg"


def test_permission_denied(tmp_path):
    import os
    import stat

    if os.name == "nt" or os.geteuid() == 0:
        return  # non testable sous Windows / root
    src = mk(tmp_path)
    ro = tmp_path / "ro"
    ro.mkdir()
    ro.chmod(stat.S_IREAD | stat.S_IEXEC)
    try:
        with pytest.raises(fm.FileOperationError):
            fm.transfer(src, ro / "Sub")
    finally:
        ro.chmod(stat.S_IRWXU)
