import os
from datetime import datetime
from pathlib import Path

import pytest
from PIL import Image

from services.date_extractor import (date_folder, date_from_filename, extract_date, parse_exif_datetime,
                                     read_meta)


def jpg(path, size=(400, 300), original=None, digitized=None, base=None, make=None, model=None, orient=None):
    exif = Image.Exif()
    sub = exif.get_ifd(0x8769)
    if original:
        sub[0x9003] = original
    if digitized:
        sub[0x9004] = digitized
    if base:
        exif[0x0132] = base
    if make:
        exif[0x010F] = make
    if model:
        exif[0x0110] = model
    if orient:
        exif[0x0112] = orient
    Image.new("RGB", size, "gray").save(path, exif=exif)
    return Path(path)


def test_parse_exif_datetime():
    assert parse_exif_datetime("2026:08:15 14:32:01") == datetime(2026, 8, 15, 14, 32, 1)
    assert parse_exif_datetime(b"2026:08:15 14:32:01\x00") == datetime(2026, 8, 15, 14, 32, 1)
    assert parse_exif_datetime("0000:00:00 00:00:00") is None
    assert parse_exif_datetime(None) is None and parse_exif_datetime(42) is None


def test_exif_priority_chain(tmp_path):
    p = jpg(tmp_path / "a.jpg", original="2026:08:15 10:00:00", digitized="2026:08:16 10:00:00",
            base="2026:08:17 10:00:00")
    d = extract_date(p)
    assert d.value == datetime(2026, 8, 15, 10) and d.source == "exif_original"
    p2 = jpg(tmp_path / "b.jpg", digitized="2026:08:16 10:00:00", base="2026:08:17 10:00:00")
    assert extract_date(p2).source == "exif_digitized"
    p3 = jpg(tmp_path / "c.jpg", base="2026:08:17 10:00:00")
    assert extract_date(p3).source == "exif_datetime"


def test_fallback_to_mtime_when_no_exif(tmp_path):
    p = tmp_path / "plain.png"
    Image.new("RGB", (10, 10)).save(p)
    ts = datetime(2020, 1, 2, 3, 4, 5).timestamp()
    os.utime(p, (ts, ts))
    d = extract_date(p)
    assert d.source == "mtime" and d.value == datetime(2020, 1, 2, 3, 4, 5)


def test_preference_mtime_and_filename(tmp_path):
    p = jpg(tmp_path / "IMG_20190305_101112.jpg", original="2026:08:15 10:00:00")
    ts = datetime(2021, 6, 7, 8, 9, 10).timestamp()
    os.utime(p, (ts, ts))
    assert extract_date(p, "mtime").value == datetime(2021, 6, 7, 8, 9, 10)
    d = extract_date(p, "filename")
    assert d.source == "filename" and d.value == datetime(2019, 3, 5, 10, 11, 12)
    with pytest.raises(ValueError):
        extract_date(p, "nimporte")


def test_filename_parsing():
    assert date_from_filename("PXL_20260815_143201123.jpg") == datetime(2026, 8, 15, 14, 32, 1)
    assert date_from_filename("2026-08-15 photo.jpg") == datetime(2026, 8, 15)
    assert date_from_filename("photo_2026_08_15.png") == datetime(2026, 8, 15)
    assert date_from_filename("IMG_4821.jpg") is None
    assert date_from_filename("20261340.jpg") is None  # mois 13 invalide


def test_date_folder_structures():
    dt = datetime(2026, 8, 15)
    assert date_folder(dt, "ymd") == Path("2026") / "08 - Août" / "2026-08-15"
    assert date_folder(dt, "ym") == Path("2026-08")
    with pytest.raises(ValueError):
        date_folder(dt, "x")


def test_meta_orientation_and_camera(tmp_path):
    land = read_meta(jpg(tmp_path / "l.jpg", (400, 300), make="Canon", model="Canon EOS R5"))
    assert land.orientation == "paysage" and land.camera == "Canon EOS R5"
    port = read_meta(jpg(tmp_path / "p.jpg", (300, 400), make="FUJIFILM", model="X100V"))
    assert port.orientation == "portrait" and port.camera == "FUJIFILM X100V"
    rotated = read_meta(jpg(tmp_path / "r.jpg", (400, 300), orient=6))  # affichée en portrait
    assert (rotated.width, rotated.height) == (300, 400) and rotated.orientation == "portrait"
    assert read_meta(jpg(tmp_path / "s.jpg", (500, 490))).orientation == "carre"


def test_corrupt_file_does_not_raise(tmp_path):
    bad = tmp_path / "bad.jpg"
    bad.write_bytes(b"pas une image")
    m = read_meta(bad)
    assert m.orientation == "inconnu" and m.date_source in ("mtime", "ctime") and m.camera is None
