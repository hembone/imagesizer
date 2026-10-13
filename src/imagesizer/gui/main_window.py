from __future__ import annotations

import copy
from pathlib import Path

from PySide6.QtCore import QRectF, QSize, Qt, QTimer
from PySide6.QtGui import QAction, QBrush, QColor, QImageReader, QKeySequence, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView, QComboBox, QDialog, QDialogButtonBox, QFileDialog, QFormLayout, QHBoxLayout, QInputDialog,
    QLabel, QLayout, QLineEdit, QListWidget, QListWidgetItem, QMainWindow, QMessageBox, QProgressBar, QPushButton,
    QScrollArea, QSplitter, QStyle, QVBoxLayout, QWidget,
)

from .. import __version__, config
from ..engine import platform
from ..engine.upscayl import Engine, default_engine_dir
from ..processing.naming import TemplateError
from ..processing.pipeline import INPUT_EXTENSIONS, ImageResult, Pipeline, collect_inputs, planned_size
from ..processing.ratios import Ratio
from . import theme
from .fit_panel import FitPanel
from .output_panel import OutputPanel
from .preview import PreviewWidget
from .ratio_panel import RatioPanel
from .upscale_panel import UpscalePanel
from .worker import BatchWorker, DownloadWorker

PATH_ROLE = Qt.ItemDataRole.UserRole
THUMB_ROLE = Qt.ItemDataRole.UserRole + 1
THUMB_SIZE = 40
THUMBS_PER_TICK = 4


class FileList(QListWidget):
    """Input list that accepts dropped files and folders."""

    def __init__(self, on_paths, parent: QWidget | None = None):
        super().__init__(parent)
        self.on_paths = on_paths
        self.locked = False  # set while a batch runs: rows map to batch indices and must not move
        self.setAcceptDrops(True)
        self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.setIconSize(QSize(THUMB_SIZE, THUMB_SIZE))
        self.setSpacing(1)

    def dragEnterEvent(self, e):
        if self.locked:
            e.ignore()
        elif e.mimeData().hasUrls():
            e.acceptProposedAction()
        else:
            super().dragEnterEvent(e)

    def dragMoveEvent(self, e):
        if self.locked:
            e.ignore()
        elif e.mimeData().hasUrls():
            e.acceptProposedAction()
        else:
            super().dragMoveEvent(e)

    def dropEvent(self, e):
        if self.locked:
            e.ignore()
        elif e.mimeData().hasUrls():
            self.on_paths([u.toLocalFile() for u in e.mimeData().urls() if u.isLocalFile()])
            e.acceptProposedAction()
        else:
            super().dropEvent(e)

    def paintEvent(self, e):
        super().paintEvent(e)
        if self.count() == 0:
            p = QPainter(self.viewport())
            p.setRenderHint(QPainter.RenderHint.Antialiasing)
            pen = QPen(QColor(theme.BORDER), 1.5, Qt.PenStyle.DashLine)
            p.setPen(pen)
            p.drawRoundedRect(QRectF(self.viewport().rect()).adjusted(8, 8, -8, -8), 8, 8)
            rect = self.viewport().rect()
            title = p.font()
            title.setPointSizeF(title.pointSizeF() * 1.15)
            title.setBold(True)
            p.setFont(title)
            p.setPen(QColor(theme.TEXT))
            p.drawText(rect.adjusted(0, 0, 0, -24), Qt.AlignmentFlag.AlignCenter, "Drop images or folders here")
            p.setFont(self.font())
            p.setPen(QColor(theme.MUTED))
            p.drawText(rect.adjusted(0, 24, 0, 0), Qt.AlignmentFlag.AlignCenter, "or use Add images… below")


class EngineDialog(QDialog):
    def __init__(self, settings: config.Settings, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle("Upscayl engine")
        self.binary = QLineEdit(settings.engine_binary)
        self.models = QLineEdit(settings.engine_models_dir)
        default = default_engine_dir()
        self.binary.setPlaceholderText(str(default / platform.exe_name()))
        self.models.setPlaceholderText(str(default / "models"))
        form = QFormLayout(self)
        intro = QLabel("Leave empty to use the downloaded engine. To reuse an installed Upscayl app, "
                       "point these at its <i>upscayl-bin</i> and <i>models</i> folder.")
        intro.setWordWrap(True)
        form.addRow(intro)
        form.addRow("upscayl-bin", self._row(self.binary, file=True))
        form.addRow("Models folder", self._row(self.models, file=False))
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)
        self.resize(640, self.sizeHint().height())

    def _row(self, edit: QLineEdit, file: bool) -> QWidget:
        btn = QPushButton("Browse…")

        def browse():
            if file:
                path, _ = QFileDialog.getOpenFileName(self, "upscayl-bin", edit.text())
            else:
                path = QFileDialog.getExistingDirectory(self, "Models folder", edit.text())
            if path:
                edit.setText(path)

        btn.clicked.connect(browse)
        w = QWidget()
        lay = QHBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(edit, 1)
        lay.addWidget(btn)
        return w


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"ImageSizer {__version__}")
        self.settings = config.load()
        self.engine = self._make_engine()
        self.worker: BatchWorker | None = None
        self.downloader: DownloadWorker | None = None
        self._loading = False
        self._save_timer = QTimer(self, singleShot=True, interval=600, timeout=self._save)
        # Next row to give a thumbnail. A row cursor rather than a list of items: Python references to items the
        # list owns can be freed twice when a window is garbage-collected.
        self._thumb_row = 0
        self._thumb_timer = QTimer(self, interval=0, timeout=self._load_thumbs)

        # --- left: inputs + preview ---
        self.files = FileList(self.add_paths)
        self.files.currentItemChanged.connect(self._refresh_preview)
        add_files = QPushButton(self.style().standardIcon(QStyle.StandardPixmap.SP_FileIcon), "Add images…")
        add_folder = QPushButton(self.style().standardIcon(QStyle.StandardPixmap.SP_DirIcon), "Add folder…")
        remove = QPushButton("Remove")
        clear = QPushButton("Clear")
        add_files.clicked.connect(self._add_files_dialog)
        add_folder.clicked.connect(self._add_folder_dialog)
        remove.clicked.connect(self._remove_selected)
        clear.clicked.connect(self._clear)
        file_buttons = QHBoxLayout()
        self.file_buttons = (add_files, add_folder, remove, clear)
        for b in self.file_buttons:
            file_buttons.addWidget(b)

        self.preview_ratio = QComboBox()
        self.preview_ratio.currentIndexChanged.connect(self._refresh_overlay)
        self.preview = PreviewWidget()
        preview_head = QHBoxLayout()
        preview_title = QLabel("PREVIEW")
        preview_title.setObjectName("sectionTitle")
        preview_head.addWidget(preview_title)
        preview_head.addStretch(1)
        preview_head.addWidget(self.preview_ratio)

        left = QWidget()
        lv = QVBoxLayout(left)
        lv.setContentsMargins(16, 16, 8, 16)
        lv.setSpacing(10)
        lv.addWidget(self.files, 2)
        lv.addLayout(file_buttons)
        lv.addLayout(preview_head)
        lv.addWidget(self.preview, 3)

        # --- right: settings ---
        self.preset_combo = QComboBox()
        self.preset_combo.setPlaceholderText("Presets")
        self.preset_combo.activated.connect(self._load_preset)
        save_preset = QPushButton("Save preset…")
        delete_preset = QPushButton("Delete")
        save_preset.clicked.connect(self._save_preset)
        delete_preset.clicked.connect(self._delete_preset)
        self.preset_controls = (self.preset_combo, save_preset, delete_preset)
        preset_row = QHBoxLayout()
        preset_title = QLabel("PRESET")
        preset_title.setObjectName("sectionTitle")
        preset_row.addWidget(preset_title)
        preset_row.addWidget(self.preset_combo, 1)
        preset_row.addWidget(save_preset)
        preset_row.addWidget(delete_preset)

        self.upscale_panel = UpscalePanel()
        self.ratio_panel = RatioPanel()
        self.fit_panel = FitPanel()
        self.output_panel = OutputPanel()
        self.upscale_panel.download_requested.connect(self._download_engine)
        self.upscale_panel.engine_settings_requested.connect(self._engine_settings)
        self.output_panel.open_requested.connect(self._open_output)
        for panel in (self.upscale_panel, self.ratio_panel, self.fit_panel, self.output_panel):
            panel.changed.connect(self._on_settings_changed)

        settings_box = QWidget()
        rv = QVBoxLayout(settings_box)
        rv.setSizeConstraint(QLayout.SizeConstraint.SetMinimumSize)  # scroll instead of squashing rows
        rv.setContentsMargins(8, 16, 16, 16)
        rv.setSpacing(12)
        rv.addLayout(preset_row)
        for panel in (self.upscale_panel, self.ratio_panel, self.fit_panel, self.output_panel):
            rv.addWidget(panel)
        rv.addStretch(1)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(settings_box)

        splitter = QSplitter()
        splitter.addWidget(left)
        splitter.addWidget(scroll)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 1)

        # --- bottom: run bar ---
        self.progress = QProgressBar()
        self.progress.setTextVisible(False)
        self.status = QLabel("Ready")
        self.status.setObjectName("muted")
        self.run_btn = QPushButton("Process images")
        self.run_btn.setDefault(True)
        self.run_btn.setProperty("primary", True)
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setEnabled(False)
        self.run_btn.clicked.connect(self._run)
        self.cancel_btn.clicked.connect(self._cancel)
        run_bar = QWidget()
        run_bar.setObjectName("runBar")
        run_bar.setAttribute(Qt.WidgetAttribute.WA_StyledBackground)
        bottom = QHBoxLayout(run_bar)
        bottom.setContentsMargins(16, 12, 16, 12)
        bottom.setSpacing(12)
        bottom.addWidget(self.status, 2)
        bottom.addWidget(self.progress, 3)
        bottom.addWidget(self.cancel_btn)
        bottom.addWidget(self.run_btn)

        central = QWidget()
        cv = QVBoxLayout(central)
        cv.setContentsMargins(0, 0, 0, 0)
        cv.setSpacing(0)
        cv.addWidget(splitter, 1)
        cv.addWidget(run_bar)
        self.setCentralWidget(central)

        quit_action = QAction("Quit", self, shortcut=QKeySequence.StandardKey.Quit, triggered=self.close)
        self.addAction(quit_action)

        self.upscale_panel.set_engine(self.engine)
        self._load_into_panels(self.settings.current)
        self._refresh_presets()
        self.resize(1200, 820)

    # --- engine -------------------------------------------------------------

    def _make_engine(self) -> Engine:
        return Engine.locate(self.settings.engine_binary or None, self.settings.engine_models_dir or None)

    def _download_engine(self) -> None:
        if self.downloader is not None:
            self.downloader.cancel.set()
            return
        self.downloader = DownloadWorker(self.engine)
        self.downloader.progress.connect(self._download_progress)
        self.downloader.failed.connect(lambda msg: QMessageBox.warning(self, "Upscayl engine", msg))
        self.downloader.finished.connect(self._download_finished)
        self.upscale_panel.download.setText("Cancel download")
        self.upscale_panel.engine_btn.setEnabled(False)
        self.run_btn.setEnabled(False)
        self.downloader.start()

    def offer_engine_download(self) -> None:
        """First-run convenience: offer to fetch the engine instead of making people find the button."""
        if self.engine.ready or self.settings.engine_prompt_dismissed or self.downloader is not None:
            return
        if self._ask_engine_download():
            self._download_engine()
        else:
            self.settings.engine_prompt_dismissed = True
            self._save()

    def _ask_engine_download(self) -> bool:
        box = QMessageBox(QMessageBox.Icon.Question, "Upscaling engine",
                          "Download the AI upscaling engine now?\n\n"
                          "It's about 215 MB and only needs to be downloaded once. You can also do this later "
                          "with “Download engine” in the Upscale panel, or crop and resize without it.", parent=self)
        download = box.addButton("Download", QMessageBox.ButtonRole.AcceptRole)
        box.addButton("Later", QMessageBox.ButtonRole.RejectRole)
        box.setDefaultButton(download)
        box.exec()
        return box.clickedButton() is download

    def _download_progress(self, msg: str, frac: float) -> None:
        self.status.setText(msg)
        self.progress.setValue(round(frac * 100))

    def _download_finished(self) -> None:
        cancelled = self.downloader.cancel.is_set()
        self.downloader.wait()  # `finished` fires just before the thread exits; never free a running QThread
        self.downloader = None
        self.run_btn.setEnabled(True)
        self.upscale_panel.engine_btn.setEnabled(True)
        self.progress.setValue(0)
        if cancelled:
            self.status.setText("Download cancelled")
        else:
            self.status.setText("Engine ready" if self.engine.ready else "Engine not installed")
        self.upscale_panel.set_engine(self.engine)
        self._on_settings_changed()

    def _engine_settings(self) -> None:
        dlg = EngineDialog(self.settings, self)
        if dlg.exec():
            self.settings.engine_binary = dlg.binary.text().strip()
            self.settings.engine_models_dir = dlg.models.text().strip()
            self.engine = self._make_engine()
            self.upscale_panel.set_engine(self.engine)
            self._on_settings_changed()

    # --- inputs ---------------------------------------------------------------

    def add_paths(self, paths: list[str]) -> None:
        if self.files.locked:
            return
        existing = {self.files.item(i).data(PATH_ROLE) for i in range(self.files.count())}
        added = 0
        for path in collect_inputs(paths):
            if str(path) in existing:
                continue
            item = QListWidgetItem(path.name)
            item.setData(PATH_ROLE, str(path))
            item.setToolTip(str(path))
            item.setIcon(theme.icon(self._blank_thumb()))
            self.files.addItem(item)
            added += 1
        if added:
            self._thumb_timer.start()
        if added and self.files.currentRow() < 0:
            self.files.setCurrentRow(0)
        self.status.setText(f"{self.files.count()} images")
        self._update_names()

    def _blank_thumb(self) -> QPixmap:
        pm = QPixmap(THUMB_SIZE, THUMB_SIZE)
        pm.fill(Qt.GlobalColor.transparent)
        p = QPainter(pm)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(QColor(theme.SURFACE_2)))
        p.drawRoundedRect(QRectF(pm.rect()), 6, 6)
        p.end()
        return pm

    def _load_thumbs(self) -> None:
        """Fill list thumbnails a few at a time so adding a big folder doesn't freeze the window."""
        loaded = 0
        while loaded < THUMBS_PER_TICK:
            if self._thumb_row >= self.files.count():
                self._thumb_timer.stop()
                return
            item = self.files.item(self._thumb_row)
            self._thumb_row += 1
            if item.data(THUMB_ROLE) is not None:  # done already (False marks one that couldn't be read)
                continue
            loaded += 1
            item.setData(THUMB_ROLE, False)
            reader = QImageReader(item.data(PATH_ROLE))
            reader.setAutoTransform(True)
            size = reader.size()
            if size.isValid():
                reader.setScaledSize(size.scaled(THUMB_SIZE * 2, THUMB_SIZE * 2, Qt.AspectRatioMode.KeepAspectRatio))
            img = reader.read()
            if img.isNull():
                continue
            # center-crop to a rounded square so every row lines up
            side = min(img.width(), img.height())
            img = img.copy((img.width() - side) // 2, (img.height() - side) // 2, side, side)
            pm = QPixmap(THUMB_SIZE, THUMB_SIZE)
            pm.fill(Qt.GlobalColor.transparent)
            p = QPainter(pm)
            p.setRenderHints(QPainter.RenderHint.Antialiasing | QPainter.RenderHint.SmoothPixmapTransform)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QBrush(img.scaled(THUMB_SIZE, THUMB_SIZE, Qt.AspectRatioMode.IgnoreAspectRatio,
                                         Qt.TransformationMode.SmoothTransformation)))
            p.drawRoundedRect(QRectF(pm.rect()), 6, 6)
            p.end()
            item.setData(THUMB_ROLE, pm)
            item.setIcon(theme.icon(pm))

    def _thumb(self, item: QListWidgetItem) -> QPixmap:
        return item.data(THUMB_ROLE) or self._blank_thumb()

    def _add_files_dialog(self) -> None:
        exts = " ".join(f"*{e}" for e in sorted(INPUT_EXTENSIONS))
        paths, _ = QFileDialog.getOpenFileNames(self, "Add images", "", f"Images ({exts})")
        self.add_paths(paths)

    def _add_folder_dialog(self) -> None:
        d = QFileDialog.getExistingDirectory(self, "Add folder")
        if d:
            self.add_paths([d])

    def _remove_selected(self) -> None:
        for item in self.files.selectedItems():
            self.files.takeItem(self.files.row(item))
        self._thumb_row = 0  # rows shifted; rows that are done get skipped cheaply
        if self.files.count():
            self._thumb_timer.start()
        self._update_names()

    def _clear(self) -> None:
        self._thumb_row = 0
        self._thumb_timer.stop()
        self.files.clear()
        self.preview.set_image(None)
        self._update_names()

    def _file_paths(self) -> list[Path]:
        return [Path(self.files.item(i).data(PATH_ROLE)) for i in range(self.files.count())]

    def _current_path(self) -> Path | None:
        item = self.files.currentItem() or (self.files.item(0) if self.files.count() else None)
        return Path(item.data(PATH_ROLE)) if item else None

    # --- settings sync ----------------------------------------------------------

    def _load_into_panels(self, preset: config.Preset) -> None:
        self._loading = True
        self.upscale_panel.load(preset.upscale)
        self.ratio_panel.load(preset.ratios)
        self.fit_panel.load(preset.fit)
        self.output_panel.load(preset.output)
        self._loading = False
        self._on_settings_changed()

    def _collect(self) -> config.Preset:
        p = self.settings.current
        self.upscale_panel.apply(p.upscale)
        p.ratios = self.ratio_panel.specs()
        self.fit_panel.apply(p.fit)
        self.output_panel.apply(p.output)
        return p

    def _on_settings_changed(self) -> None:
        if self._loading:
            return
        self._collect()
        self._refresh_preview_ratios()
        self._refresh_overlay()
        self._update_names()
        self._save_timer.start()

    def _save(self) -> None:
        try:
            config.save(self.settings)
        except OSError as e:
            self.status.setText(f"Could not save settings: {e}")

    # --- preview ------------------------------------------------------------------

    def _refresh_preview(self) -> None:
        self.preview.set_image(self._current_path())
        self._refresh_overlay()
        self._update_names()

    def _refresh_preview_ratios(self) -> None:
        current = self.preview_ratio.currentData()
        self.preview_ratio.blockSignals(True)
        self.preview_ratio.clear()
        for spec in self.settings.current.ratios:
            if not spec.enabled:
                continue
            try:
                ratio = spec.size().effective_ratio(spec.parsed())
            except ValueError:
                continue
            self.preview_ratio.addItem(ratio.label, ratio.label)
        idx = self.preview_ratio.findData(current)
        self.preview_ratio.setCurrentIndex(idx if idx >= 0 else 0)
        self.preview_ratio.blockSignals(False)

    def _refresh_overlay(self) -> None:
        fit = self.settings.current.fit
        label = self.preview_ratio.currentData()
        ratio = Ratio.parse(label) if label else None
        # JPEG can't keep transparency, so show the color the bars will actually get
        transparent = fit.pad_transparent and self.settings.current.output.format != "jpg"
        color = None if transparent else QColor(fit.pad_color)
        self.preview.set_overlay(ratio, fit.mode, fit.anchor, color)

    def _update_names(self) -> None:
        preset = self.settings.current
        src = self._current_path() or Path("example.jpg")
        sizes = None
        if self._current_path() is not None and self.preview.image is not None:
            w, h = self.preview.source_size  # already EXIF-rotated, like the pipeline sees it
            scale = preset.upscale.scale if preset.upscale.enabled else 1
            sizes = {}
            for i, spec in enumerate(preset.ratios):
                try:
                    sizes[i] = planned_size(w, h, spec, preset.fit.mode, scale)
                except ValueError:
                    pass
        try:
            folder, files = Pipeline(preset).preview_names(src, 1, sizes)
            self.output_panel.set_preview(folder, files, None)
        except TemplateError as e:
            self.output_panel.set_preview("", [], str(e))

    # --- presets ------------------------------------------------------------------

    def _refresh_presets(self) -> None:
        self.preset_combo.clear()
        self.preset_combo.addItems(sorted(self.settings.presets))
        self.preset_combo.setCurrentIndex(-1)

    def _load_preset(self) -> None:
        name = self.preset_combo.currentText()
        if name in self.settings.presets:
            directory = self.settings.current.output.directory
            self.settings.current = copy.deepcopy(self.settings.presets[name])
            if not self.settings.current.output.directory:
                self.settings.current.output.directory = directory
            self._load_into_panels(self.settings.current)
            self.status.setText(f"Loaded preset “{name}”")

    def _save_preset(self) -> None:
        name, ok = QInputDialog.getText(self, "Save preset", "Preset name:", text=self.preset_combo.currentText())
        name = name.strip()
        if not ok or not name:
            return
        if name in self.settings.presets and QMessageBox.question(
                self, "Save preset", f"Replace preset “{name}”?") != QMessageBox.StandardButton.Yes:
            return
        self.settings.presets[name] = copy.deepcopy(self._collect())
        self._save()
        self._refresh_presets()
        self.preset_combo.setCurrentText(name)

    def _delete_preset(self) -> None:
        name = self.preset_combo.currentText()
        if name in self.settings.presets and QMessageBox.question(
                self, "Delete preset", f"Delete preset “{name}”?") == QMessageBox.StandardButton.Yes:
            del self.settings.presets[name]
            self._save()
            self._refresh_presets()

    # --- running ------------------------------------------------------------------

    def _open_output(self) -> None:
        d = Path(self.settings.current.output.directory)
        d.mkdir(parents=True, exist_ok=True)
        platform.open_in_file_manager(d)

    def _run(self) -> None:
        files = self._file_paths()
        if not files:
            QMessageBox.information(self, "ImageSizer", "Add some images first.")
            return
        preset = copy.deepcopy(self._collect())
        errors = Pipeline(preset, self.engine).validate()
        if errors:
            QMessageBox.warning(self, "Can't start", "\n".join(f"• {e}" for e in errors))
            return
        self._save()
        for i in range(self.files.count()):
            item = self.files.item(i)
            item.setText(Path(item.data(PATH_ROLE)).name)
            item.setIcon(theme.icon(self._thumb(item)))
            item.setData(Qt.ItemDataRole.ForegroundRole, None)
        self.results: list[ImageResult] = []
        self.worker = BatchWorker(files, preset, self.engine)
        self.worker.file_started.connect(self._file_started)
        self.worker.file_progress.connect(self._file_progress)
        self.worker.file_done.connect(self._file_done)
        self.worker.finished.connect(self._batch_finished)
        self._set_running(True)
        self.progress.setValue(0)
        self.worker.start()

    def _set_running(self, running: bool) -> None:
        self.run_btn.setEnabled(not running)
        self.cancel_btn.setEnabled(running)
        for w in (self.upscale_panel, self.ratio_panel, self.fit_panel, self.output_panel,
                  *self.file_buttons, *self.preset_controls):
            w.setEnabled(not running)
        self.files.locked = running

    def _cancel(self) -> None:
        if self.worker:
            self.worker.cancel.set()
            self.status.setText("Cancelling…")
            self.cancel_btn.setEnabled(False)

    def _file_started(self, i: int) -> None:
        self.files.setCurrentRow(i)

    def _file_progress(self, i: int, msg: str, frac: float) -> None:
        n = self.files.count()
        self.status.setText(f"[{i + 1}/{n}] {self.files.item(i).text()} — {msg}")
        self.progress.setValue(round((i + frac) / n * 100))

    def _file_done(self, i: int, res: ImageResult) -> None:
        self.results.append(res)
        item = self.files.item(i)
        name = Path(item.data(PATH_ROLE)).name
        if res.error:
            item.setIcon(theme.icon(theme.badge(self._thumb(item), theme.ERROR, "!")))
            item.setForeground(QColor(theme.ERROR))
            item.setText(f"{name} — {res.error.splitlines()[0]}")
            item.setToolTip(res.error)
        else:
            item.setIcon(theme.icon(theme.badge(self._thumb(item), theme.OK, "✓")))
            note = f" ({len(res.skipped)} skipped)" if res.skipped else ""
            item.setText(f"{name} — {len(res.outputs)} files{note}")
            item.setToolTip("\n".join([str(res.folder)] + [f"skipped: {s}" for s in res.skipped]))

    def _batch_finished(self) -> None:
        cancelled = self.worker.cancel.is_set() if self.worker else False
        if self.worker:
            self.worker.wait()  # `finished` fires just before the thread exits; never free a running QThread
        self.worker = None
        self._set_running(False)
        ok = sum(1 for r in self.results if not r.error)
        failed = sum(1 for r in self.results if r.error and r.error != "Cancelled")
        outputs = sum(len(r.outputs) for r in self.results)
        self.progress.setValue(0 if cancelled else 100)
        msg = f"{'Cancelled' if cancelled else 'Finished'}: {ok} images → {outputs} files"
        if failed:
            msg += f", {failed} failed (hover for details)"
        self.status.setText(msg)

    def closeEvent(self, event) -> None:
        if self.worker and self.worker.isRunning():
            if QMessageBox.question(self, "ImageSizer", "Processing is running. Cancel it and quit?") \
                    != QMessageBox.StandardButton.Yes:
                event.ignore()
                return
            self.worker.cancel.set()
            self.worker.wait()
        if self.downloader and self.downloader.isRunning():
            self.downloader.cancel.set()
            self.downloader.wait()
        self._collect()
        self._save()
        event.accept()
