"""Logging : console + photo_sorter.log (rotation 5 Mo, 3 backups)."""
from __future__ import annotations

import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path

LOG_NAME = "photo_sorter.log"
LOG_FORMAT = "%(asctime)s - %(levelname)s - %(module)s - %(message)s"
ENV_DEBUG = "PHOTO_SORTER_DEBUG"
_TAG = "_photosorter_handler"


def setup_logging(log_dir: Path | None = None, debug: bool = False) -> None:
    """Configure le logger racine. DEBUG via `debug=True`, `--debug` ou PHOTO_SORTER_DEBUG=1."""
    debug = debug or os.environ.get(ENV_DEBUG, "").lower() in {"1", "true", "yes", "debug"}
    root = logging.getLogger()
    for h in [h for h in root.handlers if getattr(h, _TAG, False)]:
        root.removeHandler(h)
        h.close()
    root.setLevel(logging.DEBUG if debug else logging.INFO)
    fmt = logging.Formatter(LOG_FORMAT, "%Y-%m-%d %H:%M:%S")
    handlers: list[logging.Handler] = [logging.StreamHandler()]
    if log_dir is not None:
        try:
            log_dir.mkdir(parents=True, exist_ok=True)
            handlers.append(
                RotatingFileHandler(log_dir / LOG_NAME, maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8")
            )
        except OSError:
            pass  # pas de fichier de log : la console suffit
    for h in handlers:
        h.setFormatter(fmt)
        setattr(h, _TAG, True)
        root.addHandler(h)
