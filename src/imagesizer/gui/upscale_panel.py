from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QFormLayout, QGroupBox, QHBoxLayout, QLabel, QLineEdit, QPushButton, QSpinBox, QWidget,
)

from ..config import UpscaleSettings
from ..engine.upscayl import MODELS, Engine


class UpscalePanel(QGroupBox):
    changed = Signal()
    download_requested = Signal()
    engine_settings_requested = Signal()

    def __init__(self, parent: QWidget | None = None):
        super().__init__("Upscale (Upscayl)", parent)
        self.enabled = QCheckBox("Upscale before resizing")
        self.model = QComboBox()
        self.scale = QComboBox()
        for s in (2, 3, 4):
            self.scale.addItem(f"{s}×", s)
        self.gpu = QLineEdit()
        self.gpu.setPlaceholderText("auto")
        self.gpu.setToolTip("GPU device id (0, 1, …). Leave empty for automatic.")
        self.tile = QSpinBox()
        self.tile.setRange(0, 4096)
        self.tile.setSingleStep(32)
        self.tile.setSpecialValueText("auto")
        self.tile.setToolTip("Lower this if upscaling runs out of GPU memory.")

        self.status = QLabel()
        self.status.setWordWrap(True)
        self.download = QPushButton("Download engine")
        self.engine_btn = QPushButton("Engine paths…")
        engine_row = QHBoxLayout()
        engine_row.addWidget(self.status, 1)
        engine_row.addWidget(self.download)
        engine_row.addWidget(self.engine_btn)

        form = QFormLayout(self)
        form.addRow(self.enabled)
        form.addRow("Model", self.model)
        form.addRow("Scale", self.scale)
        form.addRow("GPU", self.gpu)
        form.addRow("Tile size", self.tile)
        form.addRow(engine_row)

        self.enabled.toggled.connect(self._update_enabled)
        for sig in (self.enabled.toggled, self.model.currentIndexChanged, self.scale.currentIndexChanged,
                    self.gpu.textChanged, self.tile.valueChanged):
            sig.connect(self.changed)
        self.download.clicked.connect(self.download_requested)
        self.engine_btn.clicked.connect(self.engine_settings_requested)

    def set_engine(self, engine: Engine) -> None:
        installed = set(engine.installed_models())
        current = self.model.currentData()
        self.model.blockSignals(True)
        self.model.clear()
        names = list(MODELS) + sorted(installed - set(MODELS))  # custom models dropped into the folder
        for name in names:
            label = MODELS.get(name, name)
            self.model.addItem(label if name in installed else f"{label} (not installed)", name)
        if current:
            self.model.setCurrentIndex(max(0, self.model.findData(current)))
        self.model.blockSignals(False)

        if engine.ready:
            self.status.setText(f"Engine ready · {len(installed)} models")
            self.download.setVisible(len(installed) < len(MODELS))
            self.download.setText("Download missing models")
        else:
            self.status.setText("Engine not installed" if not engine.has_binary else "No models installed")
            self.download.setVisible(True)
            self.download.setText("Download engine")

    def _update_enabled(self, on: bool) -> None:
        for w in (self.model, self.scale, self.gpu, self.tile):
            w.setEnabled(on)

    def load(self, s: UpscaleSettings) -> None:
        self.enabled.setChecked(s.enabled)
        self._update_enabled(s.enabled)
        self.model.setCurrentIndex(max(0, self.model.findData(s.model)))
        self.scale.setCurrentIndex(max(0, self.scale.findData(s.scale)))
        self.gpu.setText("" if s.gpu_id == "auto" else s.gpu_id)
        self.tile.setValue(s.tile_size)

    def apply(self, s: UpscaleSettings) -> None:
        s.enabled = self.enabled.isChecked()
        s.model = self.model.currentData() or s.model
        s.scale = self.scale.currentData()
        s.gpu_id = self.gpu.text().strip() or "auto"
        s.tile_size = self.tile.value()
