import os
import time

import pytest
from PIL import Image

from services.thumbnail_cache import THUMB_SIZES, ThumbnailCache, ThumbnailError


def make_img(path, size=(800, 400), color="red", mode="RGB"):
    Image.new(mode, size, color).save(path)
    return path


def test_generate_and_reuse(tmp_path):
    src = make_img(tmp_path / "a.png")
    cache = ThumbnailCache(tmp_path / "cache")
    t1 = cache.get(src, 128)
    with Image.open(t1) as im:
        assert im.format == "JPEG" and max(im.size) == 128 and im.size == (128, 64)
    mtime = t1.stat().st_mtime_ns
    assert cache.get(src, 128) == t1 and t1.stat().st_mtime_ns == mtime  # pas régénérée
    assert cache.is_fresh(src, 128) and not cache.is_fresh(src, 256)


def test_all_sizes_and_invalid_size(tmp_path):
    src = make_img(tmp_path / "a.png", (1000, 1000))
    cache = ThumbnailCache(tmp_path / "cache")
    for px in THUMB_SIZES:
        assert cache.get(src, px).exists()
    with pytest.raises(ValueError):
        cache.get(src, 100)


def test_invalidation_when_source_changes(tmp_path):
    src = make_img(tmp_path / "a.png", (600, 600), "red")
    cache = ThumbnailCache(tmp_path / "cache")
    old = cache.get(src, 128)
    make_img(src, (900, 900), "blue")
    os.utime(src, (time.time() + 10, time.time() + 10))
    assert not cache.is_fresh(src, 128)
    new = cache.get(src, 128)
    assert new != old and not old.exists()  # ancienne version supprimée
    assert Image.open(new).getpixel((10, 10))[2] > 200  # bleu


def test_rgba_and_exif_orientation(tmp_path):
    rgba = make_img(tmp_path / "t.png", (200, 100), (255, 0, 0, 0), "RGBA")
    cache = ThumbnailCache(tmp_path / "cache")
    assert Image.open(cache.get(rgba, 128)).getpixel((5, 5))[0] > 240  # fond blanc, pas noir
    exif = Image.Exif()
    exif[0x0112] = 6  # rotation 90°
    jpg = tmp_path / "r.jpg"
    Image.new("RGB", (400, 200), "green").save(jpg, exif=exif)
    assert Image.open(cache.get(jpg, 128)).size == (64, 128)


def test_lru_trim_and_clear(tmp_path):
    cache = ThumbnailCache(tmp_path / "cache", max_bytes=10**9)
    srcs = [make_img(tmp_path / f"{i}.png", (500, 500), (i * 40, 90, 200)) for i in range(4)]
    thumbs = []
    for i, s in enumerate(srcs):
        t = cache.get(s, 128)
        os.utime(t, ns=(1_000_000_000 * (i + 1), t.stat().st_mtime_ns))  # atime croissant
        thumbs.append(t)
    cache.max_bytes = thumbs[2].stat().st_size + thumbs[3].stat().st_size + 1  # garde les 2 plus récentes
    assert cache.trim() == 2
    assert not thumbs[0].exists() and not thumbs[1].exists() and thumbs[2].exists() and thumbs[3].exists()
    assert cache.size_bytes() <= cache.max_bytes
    assert cache.clear() == 2 and cache.size_bytes() == 0


def test_errors(tmp_path):
    cache = ThumbnailCache(tmp_path / "cache")
    with pytest.raises(FileNotFoundError):
        cache.get(tmp_path / "absent.jpg")
    bad = tmp_path / "bad.jpg"
    bad.write_bytes(b"pas une image")
    with pytest.raises(ThumbnailError):
        cache.get(bad)
    assert list((tmp_path / "cache").glob("*.tmp")) == []
