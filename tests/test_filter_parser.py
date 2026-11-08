from datetime import datetime, timedelta
from pathlib import Path

import pytest

from services.date_extractor import PhotoMeta
from services.filter_parser import (FilterContext, FilterError, command, commands, parse, parse_size,
                                    suggest)

NOW = datetime(2026, 8, 20, 12, 0)
CTX = FilterContext(now=NOW)


def meta(name="a.jpg", date=datetime(2026, 8, 15, 10), w=400, h=300, size=1_000_000, camera=None,
         added=datetime(2026, 8, 1)):
    return PhotoMeta(Path(name), size, date, added, date, "exif_original", w, h, camera)


def ok(text, m):
    return parse(text, CTX).matches(m)


def test_empty_filter_matches_all():
    f = parse("")
    assert f.is_empty and f.matches(meta()) and f.describe() == "aucun filtre"


def test_date_commands():
    m = meta(date=datetime(2026, 8, 15, 10))
    assert ok(":date 2026-08", m) and ok(":date 2026-08-15", m) and ok(":date 2026", m)
    assert not ok(":date 2026-09", m) and not ok(":date 2026-08-16", m)
    assert ok(":date >2026-08-14", m) and not ok(":date >2026-08-15", m)
    assert ok(":date <2026-08-16", m) and not ok(":date <2026-08-15", m)
    assert ok(":date >2026-07", m)  # après la fin de juillet


def test_orientation_commands():
    assert ok(":portrait", meta(w=300, h=400)) and not ok(":portrait", meta())
    assert ok(":paysage", meta()) and not ok(":paysage", meta(w=300, h=400))
    assert ok(":carre", meta(w=500, h=490)) and not ok(":carre", meta())
    assert not ok(":portrait", meta(w=0, h=0))  # inconnu


def test_size_commands():
    assert ok(":grand", meta(size=6 * 1024 * 1024)) and not ok(":grand", meta())
    assert ok(":grand 500ko", meta(size=600 * 1024))
    assert ok(":petit", meta(size=100 * 1024)) and not ok(":petit", meta())
    assert parse_size("2.5 Mo") == int(2.5 * 1024**2) and parse_size("10MB") == 10 * 1024**2
    with pytest.raises(FilterError):
        parse_size("beaucoup")


def test_recent_and_new():
    assert ok(":nouveau", meta(added=NOW)) and not ok(":nouveau", meta())
    assert ok(":recent", meta(added=NOW - timedelta(days=3))) and not ok(":recent", meta(added=NOW - timedelta(days=9)))
    assert ok(":recent 30", meta(added=NOW - timedelta(days=9)))


def test_camera_and_quotes():
    m = meta(camera="Canon EOS R5")
    assert ok(":camera canon", m) and ok(':camera "eos r5"', m) and not ok(":camera nikon", m)
    assert not ok(":camera canon", meta(camera=None))


def test_and_or_not_toutes():
    land_big = meta(size=9 * 1024**2)
    assert ok(":paysage :grand", land_big) and not ok(":portrait :grand", land_big)
    assert ok(":portrait | :grand", land_big)           # OU
    assert ok("-:portrait", land_big)
    assert not ok("-:paysage", land_big)
    assert ok(":portrait :grand :toutes", meta())       # :toutes remet à zéro
    assert not ok(":toutes :portrait", meta())


def test_describe():
    assert parse(":date 2026-08 -:grand | :portrait", CTX).describe() == "date 2026-08 ET NON grand  OU  portrait"


def test_errors_with_suggestion():
    with pytest.raises(FilterError) as e:
        parse(":portrai")
    assert ":portrait" in str(e.value)
    for bad in (":date", ":date 2026-13", ":date >nimporte", "orphelin", ':camera "oups', ":camera", ":recent abc"):
        with pytest.raises(FilterError):
            parse(bad, CTX)


def test_autocomplete_and_registry():
    assert suggest("po") == [":portrait"] and ":paysage" in suggest("pa") and ":date" in suggest(":d")
    assert {c.name for c in commands()} >= {"date", "portrait", "paysage", "carre", "grand", "petit", "nouveau",
                                            "recent", "camera", "toutes"}


def test_custom_command_is_trivial_to_add():
    @command("pdf", help="test")
    def _pdf(args, ctx):
        return lambda m: m.path.suffix == ".pdf"

    assert ok(":pdf", meta(name="x.pdf")) and not ok(":pdf", meta())


def test_apply_returns_subset():
    items = [meta("a.jpg"), meta("b.jpg", w=300, h=400), meta("c.jpg", w=300, h=400)]
    assert [m.path.name for m in parse(":portrait", CTX).apply(items)] == ["b.jpg", "c.jpg"]


def test_tab_completion():
    from services.filter_parser import complete

    assert complete(":por") == ":portrait "           # unique -> complet + espace
    assert complete(":date 2026-08 :pay") == ":date 2026-08 :paysage "
    assert complete("-:gr") == "-:grand "
    assert complete(":p") == ":p"                      # plusieurs (paysage, portrait, petit) : préfixe commun = ":p"
    assert complete(":xyz") == ":xyz" and complete("") == "" and complete(":portrait ") == ":portrait "
    assert complete(":ca") == ":c" + "a" and complete(":cam") == ":camera "
