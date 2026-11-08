"""Packaging : python build.py  ->  dist/PhotoSorterStudio (nécessite PyInstaller)."""
import subprocess
import sys

CMD = [
    sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--windowed",
    "--name", "PhotoSorterStudio", "main.py",
]

if __name__ == "__main__":
    sys.exit(subprocess.call(CMD))
