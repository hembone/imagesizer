from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFontDatabase
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QFileDialog, QFormLayout, QGroupBox, QHBoxLayout, QLabel, QLineEdit, QPushButton, QSpinBox,
    QWidget,
)

from ..config import OutputSettings
from ..processing.naming import FILE_TOKENS, FOLDER_TOKENS
from . import theme


def _combo(items: list[tuple[str, str]]) -> QComboBox:
    c = QComboBox()
    for key, label in items:
        c.addItem(label, key)
    return c


class OutputPanel(QGroupBox):
    changed = Signal()
    open_requested = Signal()

    def __init__(self, parent: QWidget | None = None):
        super().__init__("Output", parent)
        self.directory = QLineEdit()
        browse = QPushButton("Browse…")
        open_btn = QPushButton("Open")
        dir_row = QHBoxLayout()
        dir_row.addWidget(self.directory, 1)
        dir_row.addWidget(browse)
        dir_row.addWidget(open_btn)

        self.format = _combo([("png", "PNG"), ("jpg", "JPEG"), ("webp", "WebP")])
        self.quality = theme.spin_box(QSpinBox())
        self.quality.setRange(1, 100)
        fmt_row = QHBoxLayout()
        fmt_row.addWidget(self.format)
        fmt_row.addWidget(QLabel("Quality"))
        fmt_row.addWidget(self.quality)
        fmt_row.addStretch(1)

        self.folder_template = QLineEdit()
        self.folder_template.setToolTip("Tokens: " + " ".join(f"{{{t}}}" for t in FOLDER_TOKENS))
        self.file_template = QLineEdit()
        self.file_template.setToolTip("Tokens: " + " ".join(f"{{{t}}}" for t in FILE_TOKENS))
        tokens = QLabel("Tokens: " + " ".join(f"{{{t}}}" for t in FILE_TOKENS)
                        + "\n{ratio}, {w}, {h} work in file names only.")
        tokens.setTextFormat(Qt.TextFormat.PlainText)
        tokens.setObjectName("muted")


        self.folder_collision = _combo([("reuse", "Write into it"), ("rename", "Make a new numbered folder"),
                                        ("skip", "Skip the image")])
        self.file_collision = _combo([("rename", "Add a number"), ("overwrite", "Overwrite"), ("skip", "Skip")])
        self.keep_upscaled = QCheckBox("Also save the full upscaled image")
        self.keep_metadata = QCheckBox("Keep color profile and EXIF")

        self.preview = QLabel()
        self.preview.setFont(QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont))
        self.preview.setWordWrap(True)
        self.preview.setObjectName("codeBlock")
        self.preview.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

        form = QFormLayout(self)
        form.addRow("Folder", dir_row)
        form.addRow("Format", fmt_row)
        form.addRow("Folder name", self.folder_template)
        form.addRow("File name", self.file_template)
        form.addRow("", tokens)
        form.addRow("If folder exists", self.folder_collision)
        form.addRow("If file exists", self.file_collision)
        form.addRow(self.keep_upscaled)
        form.addRow(self.keep_metadata)
        form.addRow("Preview", self.preview)

        browse.clicked.connect(self._browse)
        open_btn.clicked.connect(self.open_requested)
        self.format.currentIndexChanged.connect(self._update_quality)
        for sig in (self.directory.textChanged, self.format.currentIndexChanged, self.quality.valueChanged,
                    self.folder_template.textChanged, self.file_template.textChanged,
                    self.folder_collision.currentIndexChanged, self.file_collision.currentIndexChanged,
                    self.keep_upscaled.toggled, self.keep_metadata.toggled):
            sig.connect(self.changed)

    def _browse(self) -> None:
        d = QFileDialog.getExistingDirectory(self, "Output folder", self.directory.text())
        if d:
            self.directory.setText(d)

    def _update_quality(self) -> None:
        self.quality.setEnabled(self.format.currentData() != "png")

    def set_preview(self, folder: str, files: list[str], error: str | None) -> None:
        if error:
            self.preview.setStyleSheet(f"color: {theme.ERROR};")
            self.preview.setText(error)
            return
        self.preview.setStyleSheet("")
        lines = [f"{folder}/"] + ([f"  {f}" for f in files] or ["  (no ratios selected)"])
        self.preview.setText("\n".join(lines))

    def load(self, s: OutputSettings) -> None:
        self.directory.setText(s.directory)
        self.format.setCurrentIndex(max(0, self.format.findData(s.format)))
        self.quality.setValue(s.quality)
        self.folder_template.setText(s.folder_template)
        self.file_template.setText(s.file_template)
        self.folder_collision.setCurrentIndex(max(0, self.folder_collision.findData(s.folder_collision)))
        self.file_collision.setCurrentIndex(max(0, self.file_collision.findData(s.file_collision)))
        self.keep_upscaled.setChecked(s.keep_upscaled)
        self.keep_metadata.setChecked(s.keep_metadata)
        self._update_quality()

    def apply(self, s: OutputSettings) -> None:
        s.directory = self.directory.text().strip()
        s.format = self.format.currentData()
        s.quality = self.quality.value()
        s.folder_template = self.folder_template.text()
        s.file_template = self.file_template.text()
        s.folder_collision = self.folder_collision.currentData()
        s.file_collision = self.file_collision.currentData()
        s.keep_upscaled = self.keep_upscaled.isChecked()
        s.keep_metadata = self.keep_metadata.isChecked()
