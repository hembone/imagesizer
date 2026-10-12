"""Background threads for batch processing and engine downloads."""

from __future__ import annotations

import threading
from pathlib import Path

from PySide6.QtCore import QThread, Signal

from ..config import Preset
from ..engine.upscayl import Cancelled, Engine
from ..processing.pipeline import Pipeline


class BatchWorker(QThread):
    file_started = Signal(int)
    file_progress = Signal(int, str, float)
    file_done = Signal(int, object)  # ImageResult

    def __init__(self, files: list[Path], preset: Preset, engine: Engine | None):
        super().__init__()
        self.files = files
        self.cancel = threading.Event()
        self.pipeline = Pipeline(preset, engine, self.cancel)

    def run(self) -> None:
        # Images go one at a time: upscayl-bin already saturates the GPU, and parallel runs just fight over VRAM.
        for i, src in enumerate(self.files):
            if self.cancel.is_set():
                break
            self.file_started.emit(i)
            res = self.pipeline.process(src, i + 1, lambda msg, frac, i=i: self.file_progress.emit(i, msg, frac))
            self.file_done.emit(i, res)


class DownloadWorker(QThread):
    progress = Signal(str, float)
    failed = Signal(str)

    def __init__(self, engine: Engine):
        super().__init__()
        self.engine = engine
        self.cancel = threading.Event()

    def run(self) -> None:
        try:
            self.engine.download(progress=self.progress.emit, cancel=self.cancel)
        except Cancelled:
            self.failed.emit("Download cancelled")
        except Exception as e:
            self.failed.emit(f"Download failed: {e}")
