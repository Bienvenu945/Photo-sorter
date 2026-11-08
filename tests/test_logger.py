import logging

from logger import LOG_NAME, setup_logging


def test_log_file_format_and_debug(tmp_path):
    setup_logging(tmp_path, debug=True)
    logging.getLogger("file_manager").debug("hello é")
    for h in logging.getLogger().handlers:
        h.flush()
    text = (tmp_path / LOG_NAME).read_text("utf-8")
    assert " - DEBUG - " in text and "hello é" in text
    setup_logging(None)  # libère le fichier


def test_env_enables_debug(tmp_path, monkeypatch):
    monkeypatch.setenv("PHOTO_SORTER_DEBUG", "1")
    setup_logging(tmp_path)
    assert logging.getLogger().level == logging.DEBUG
    monkeypatch.delenv("PHOTO_SORTER_DEBUG")
    setup_logging(None)
    assert logging.getLogger().level == logging.INFO
