from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QButtonGroup, QCheckBox, QColorDialog, QFormLayout, QGridLayout, QGroupBox, QHBoxLayout, QPushButton,
    QRadioButton, QToolButton, QWidget,
)

from ..config import FitSettings

ANCHOR_GRID = [["top-left", "top", "top-right"], ["left", "center", "right"],
               ["bottom-left", "bottom", "bottom-right"]]
ANCHOR_ARROWS = {"top-left": "↖", "top": "↑", "top-right": "↗", "left": "←", "center": "●",
                 "right": "→", "bottom-left": "↙", "bottom": "↓", "bottom-right": "↘"}


class FitPanel(QGroupBox):
    changed = Signal()

    def __init__(self, parent: QWidget | None = None):
        super().__init__("Fit to ratio", parent)
        self.crop = QRadioButton("Crop (fill)")
        self.pad = QRadioButton("Pad (letterbox)")
        self.crop.setChecked(True)
        modes = QHBoxLayout()
        modes.addWidget(self.crop)
        modes.addWidget(self.pad)
        modes.addStretch(1)

        self.anchors = QButtonGroup(self)
        grid = QGridLayout()
        grid.setSpacing(2)
        for r, names in enumerate(ANCHOR_GRID):
            for c, name in enumerate(names):
                b = QToolButton()
                b.setText(ANCHOR_ARROWS[name])
                b.setToolTip(name)
                b.setCheckable(True)
                b.setFixedSize(28, 28)
                b.setProperty("anchor", name)
                self.anchors.addButton(b)
                grid.addWidget(b, r, c)
        grid.setContentsMargins(0, 0, 0, 0)
        anchor_box = QWidget()
        anchor_box.setLayout(grid)
        anchor_box.setFixedSize(anchor_box.sizeHint())

        self._color = QColor("#ffffff")
        self.color_btn = QPushButton()
        self.color_btn.setFixedWidth(80)
        self.transparent = QCheckBox("Transparent (PNG/WebP)")
        pad_row = QHBoxLayout()
        pad_row.addWidget(self.color_btn)
        pad_row.addWidget(self.transparent)
        pad_row.addStretch(1)

        form = QFormLayout(self)
        form.addRow("Mode", modes)
        form.addRow("Anchor", anchor_box)
        form.addRow("Pad color", pad_row)

        self.crop.toggled.connect(self._update_enabled)
        self.transparent.toggled.connect(self._update_enabled)
        self.color_btn.clicked.connect(self._pick_color)
        for sig in (self.crop.toggled, self.transparent.toggled, self.anchors.buttonClicked):
            sig.connect(self.changed)
        self._set_color(self._color)

    def _pick_color(self) -> None:
        c = QColorDialog.getColor(self._color, self, "Pad color")
        if c.isValid():
            self._set_color(c)
            self.changed.emit()

    def _set_color(self, c: QColor) -> None:
        self._color = c
        self.color_btn.setText(c.name())
        fg = "#000" if c.lightness() > 128 else "#fff"
        self.color_btn.setStyleSheet(f"background:{c.name()}; color:{fg};")

    def _update_enabled(self) -> None:
        pad = self.pad.isChecked()
        self.transparent.setEnabled(pad)
        self.color_btn.setEnabled(pad and not self.transparent.isChecked())

    def load(self, s: FitSettings) -> None:
        (self.pad if s.mode == "pad" else self.crop).setChecked(True)
        for b in self.anchors.buttons():
            b.setChecked(b.property("anchor") == s.anchor)
        self._set_color(QColor(s.pad_color))
        self.transparent.setChecked(s.pad_transparent)
        self._update_enabled()

    def apply(self, s: FitSettings) -> None:
        s.mode = "pad" if self.pad.isChecked() else "crop"
        checked = self.anchors.checkedButton()
        s.anchor = checked.property("anchor") if checked else "center"
        s.pad_color = self._color.name()
        s.pad_transparent = self.transparent.isChecked()
