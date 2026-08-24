"""Qt workers used for SSH and local command background tasks."""
from typing import Callable

from PySide6.QtCore import QObject, QRunnable, Signal


class WorkerSignals(QObject):
    done = Signal(object)
    error = Signal(str)
    progress = Signal(object)


class Worker(QRunnable):
    def __init__(self, task: Callable):
        super().__init__()
        self.task = task
        self.signals = WorkerSignals()

    def run(self):
        try:
            result = self.task()
        except Exception as error:
            try:
                self.signals.error.emit(str(error))
            except RuntimeError:
                pass
            return
        try:
            self.signals.done.emit(result)
        except RuntimeError:
            pass
