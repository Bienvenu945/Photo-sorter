from config import ConfigManager, validate_categories
from models import Category


def test_no_default_categories(tmp_path):
    assert ConfigManager(tmp_path).categories() == []


def test_validation():
    a, b = Category.new("A", "1"), Category.new("a", "1")
    assert len(validate_categories([a, b])) >= 2           # nom + raccourci en double
    assert validate_categories([Category.new("X", "Esc")])  # réservé
    assert validate_categories([Category.new("", "2")])     # nom vide
    assert validate_categories([Category.new("x" * 41, "2")])
    assert not validate_categories([Category.new("Famille", "1"), Category.new("Amis", "2")])


def test_save_reload_and_backup_recovery(tmp_path):
    cfg = ConfigManager(tmp_path)
    cfg.set_categories([Category.new("Famille", "1")])
    cfg.set_categories([Category.new("Famille", "1"), Category.new("Amis", "2")])
    cfg.cat_file.write_text("{corrompu", "utf-8")
    assert [c.name for c in ConfigManager(tmp_path).categories()] == ["Famille"]  # restauré depuis .bak


def test_profiles(tmp_path):
    cfg = ConfigManager(tmp_path)
    assert cfg.create_profile("Perso")
    assert not cfg.create_profile("Perso")
    assert cfg.delete_profile("Perso") and cfg.active_profile == "default"


def test_new_gui_shortcuts_are_reserved():
    for key in ("G", "F11", "Ctrl+,", "Ctrl+A", "Ctrl+H", "Ctrl+Shift+Z", "Ctrl+R", "Ctrl+B"):
        assert validate_categories([Category.new("X", key)])


def test_gui_defaults(tmp_path):
    s = ConfigManager(tmp_path).settings
    assert s["palette"] == "hyperos" and s["accent"] is None and s["thumb_size"] == 192 and s["info_panel"] is True
