import pytest

pytest.importorskip("PySide6")

import theme  # noqa: E402


def test_every_palette_generates_complete_qss():
    for key in theme.PALETTES:
        theme.set_palette(key)
        qss = theme.build_qss()
        assert "@" not in qss and "QLabel#pageTitle" in qss and "QFrame#Viewer" in qss


def test_hyperos_reference_palette():
    theme.set_palette("hyperos")
    p = theme.current()
    assert (p.bg_top, p.surface, p.card, p.accent_a, p.accent_b) == ("#0B0E14", "#151B25", "#1D2532", "#75B9FF", "#A78BFA")
    assert p.flat and not p.light and p.fg == "#F2F5FA"


def test_light_and_hacker_alternatives_exist():
    assert theme.PALETTES["hyperos_light"].light and theme.PALETTES["hacker"].accent_a == "#00FF9C"


def test_accent_override_and_fallback():
    theme.set_palette("hyperos", "#ff7a00")
    assert theme.current().accent_a == "#ff7a00" and theme.current().accent_b != "#A78BFA"
    assert "#ff7a00" in theme.build_qss()
    theme.set_palette("???")
    assert theme.current().key == "hyperos"
    theme.set_palette("hyperos", "pas-une-couleur")
    assert theme.current().accent_a == "#75B9FF"


def test_overlay_inverts_on_light_theme():
    theme.set_palette("hyperos")
    assert theme.ov(40).red() == 255
    theme.set_palette("hyperos_light")
    assert theme.ov(40).red() < 100
    theme.set_palette("hyperos")
