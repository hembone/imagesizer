from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QGroupBox, QHBoxLayout, QLabel, QPushButton, QSpinBox, QToolButton, QVBoxLayout, QWidget,
)

from ..config import RatioSpec
from ..processing.ratios import PRESETS, Ratio
from . import theme

SIZE_MODES = [("max", "Max resolution"), ("long_edge", "Long edge"), ("exact", "Exact size")]


def _spin(value: int) -> QSpinBox:
    s = QSpinBox()
    s.setRange(1, 65535)
    s.setSuffix(" px")
    s.setValue(value)
    return theme.spin_box(s)


class RatioRow(QWidget):
    changed = Signal()
    remove_requested = Signal(object)

    def __init__(self, spec: RatioSpec, parent: QWidget | None = None):
        super().__init__(parent)
        self.enabled = QCheckBox()
        self.enabled.setChecked(spec.enabled)
        self.ratio = QComboBox()
        self.ratio.setEditable(True)
        self.ratio.addItems(PRESETS)
        self.ratio.setCurrentText(spec.ratio)
        self.ratio.setMinimumContentsLength(6)
        self.ratio.setToolTip("Pick a preset or type a custom ratio such as 5:7 or 2.39:1")
        self.mode = QComboBox()
        for key, label in SIZE_MODES:
            self.mode.addItem(label, key)
        self.mode.setCurrentIndex(max(0, self.mode.findData(spec.size_mode)))
        self.long_edge = _spin(spec.long_edge)
        self.width = _spin(spec.width)
        self.times = QLabel("×")
        self.height = _spin(spec.height)
        self.remove = QToolButton()
        self.remove.setText("✕")
        self.remove.setToolTip("Remove this ratio")
        self.remove.setProperty("flat", True)

        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        for w in (self.enabled, self.ratio, self.mode, self.long_edge, self.width, self.times, self.height):
            row.addWidget(w)
        row.addStretch(1)
        row.addWidget(self.remove)

        self._update_visibility()
        self.mode.currentIndexChanged.connect(self._mode_changed)
        self.ratio.currentTextChanged.connect(self._ratio_changed)
        self.width.valueChanged.connect(self._width_changed)
        for sig in (self.enabled.toggled, self.ratio.currentTextChanged, self.mode.currentIndexChanged,
                    self.long_edge.valueChanged, self.width.valueChanged, self.height.valueChanged):
            sig.connect(self.changed)
        self.remove.clicked.connect(lambda: self.remove_requested.emit(self))

    def _parsed(self) -> Ratio | None:
        try:
            return Ratio.parse(self.ratio.currentText())
        except ValueError:
            return None

    def _update_visibility(self) -> None:
        mode = self.mode.currentData()
        self.long_edge.setVisible(mode == "long_edge")
        for w in (self.width, self.times, self.height):
            w.setVisible(mode == "exact")

    def _mode_changed(self) -> None:
        self._update_visibility()
        if self.mode.currentData() == "exact":
            self._width_changed(self.width.value())

    def _ratio_changed(self) -> None:
        valid = self._parsed() is not None
        self.ratio.setStyleSheet("" if valid else f"QComboBox {{ color: {theme.ERROR}; border-color: {theme.ERROR}; }}")
        if valid and self.mode.currentData() == "exact":
            self._width_changed(self.width.value())

    def _width_changed(self, w: int) -> None:
        """Keep exact sizes on the row's ratio as the width changes; the height can still be edited freely."""
        r = self._parsed()
        if r and self.mode.currentData() == "exact":
            self.height.blockSignals(True)
            self.height.setValue(max(1, round(w / r.value)))
            self.height.blockSignals(False)

    def spec(self) -> RatioSpec:
        return RatioSpec(self.ratio.currentText().strip(), self.enabled.isChecked(), self.mode.currentData(),
                         self.long_edge.value(), self.width.value(), self.height.value())


class RatioPanel(QGroupBox):
    changed = Signal()

    def __init__(self, parent: QWidget | None = None):
        super().__init__("Aspect ratios — one output file per checked ratio", parent)
        self.rows_layout = QVBoxLayout()
        self.rows: list[RatioRow] = []
        add = QPushButton("+ Add ratio")
        add.clicked.connect(lambda: self._add(RatioSpec("3:2")))
        lay = QVBoxLayout(self)
        lay.addLayout(self.rows_layout)
        lay.addWidget(add)

    def _add(self, spec: RatioSpec, emit: bool = True) -> None:
        row = RatioRow(spec)
        row.changed.connect(self.changed)
        row.remove_requested.connect(self._remove)
        self.rows.append(row)
        self.rows_layout.addWidget(row)
        if emit:
            self.changed.emit()

    def _remove(self, row: RatioRow) -> None:
        self.rows.remove(row)
        row.deleteLater()
        self.changed.emit()

    def load(self, specs: list[RatioSpec]) -> None:
        for row in self.rows:
            row.deleteLater()
        self.rows = []
        for spec in specs:
            self._add(spec, emit=False)

    def specs(self) -> list[RatioSpec]:
        return [row.spec() for row in self.rows]
