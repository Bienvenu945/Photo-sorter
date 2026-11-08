"""Calculs hors du thread UI, avec progression et annulation automatique (le plus récent gagne)."""
from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal


class _Signals(QObject):
    progress = Signal(int, int, int)  # génération, faits, total
    result = Signal(int, object)
    failed = Signal(int, str)


class _Job(QRunnable):
    def __init__(self, gen: int, fn: Callable, owner: "BackgroundCall") -> None:
        super().__init__()
        self.gen, self.fn, self.owner = gen, fn, owner

    def run(self) -> None:
        sig = self.owner._signals

        def progress(done: int, total: int) -> bool:
            sig.progress.emit(self.gen, done, total)
            return self.owner.gen == self.gen  # False : un calcul plus récent a été lancé, on peut s'arrêter

        try:
            value = self.fn(progress)
        except Exception as e:  # message affiché à l'utilisateur
            sig.failed.emit(self.gen, str(e))
            return
        if self.owner.gen == self.gen:
            sig.result.emit(self.gen, value)


class BackgroundCall(QObject):
    """``submit(fn)`` lance ``fn(progress)`` dans le pool ; seul le dernier résultat est émis."""

    progress = Signal(int, int)
    result = Signal(object)
    failed = Signal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.gen = 0
        self._signals = _Signals()
        self._signals.progress.connect(lambda g, d, t: g == self.gen and self.progress.emit(d, t))
        self._signals.result.connect(lambda g, v: g == self.gen and self.result.emit(v))
        self._signals.failed.connect(lambda g, m: g == self.gen and self.failed.emit(m))

    def submit(self, fn: Callable) -> None:
        self.gen += 1
        QThreadPool.globalInstance().start(_Job(self.gen, fn, self))
