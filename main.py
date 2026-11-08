#!/usr/bin/env python3
"""Photo Sorter Studio — point d'entrée.

Conçu par Bienvenu K.K — © 2026

    python3 main.py                  interface HyperOS-inspired (fenêtre sans cadre)
    python3 main.py --native-frame   cadre natif (si les coins apparaissent noirs)
    python3 main.py --debug          logs détaillés
"""
import argparse
import logging
import sys

from PySide6.QtWidgets import QApplication

import theme
from config import APP_NAME, APP_TITLE, ConfigManager, default_config_dir
from logger import setup_logging
from services.history_db import HistoryDB
from widgets import icons
from window import MainWindow

logger = logging.getLogger(__name__)


def main() -> int:
    parser = argparse.ArgumentParser(description=APP_TITLE)
    parser.add_argument("--debug", action="store_true", help="active les logs DEBUG")
    parser.add_argument("--native-frame", action="store_true", help="utilise le cadre de fenêtre du système")
    args, qt_args = parser.parse_known_args()

    app = QApplication([sys.argv[0], *qt_args])
    app.setOrganizationName("")
    app.setApplicationName(APP_NAME)
    config_dir = default_config_dir()
    setup_logging(config_dir, debug=args.debug)
    cfg = ConfigManager(config_dir)
    theme.set_palette(cfg.settings.get("palette", "hyperos"), cfg.settings.get("accent"))
    theme.apply(app)
    app.setWindowIcon(icons.app_icon())
    win = MainWindow(cfg, native_frame=args.native_frame, history=HistoryDB(config_dir / "history.db"))
    win.show()
    logger.info("%s démarré", APP_TITLE)
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
