"""Offscreen GUI checks: window builds, inputs load, name preview and run/validation wiring."""

import os

import pytest
from PIL import Image

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
QtWidgets = pytest.importorskip("PySide6.QtWidgets")


@pytest.fixture
def window(tmp_path, monkeypatch, qapp):
    from imagesizer import config
    from imagesizer.gui.main_window import MainWindow

    monkeypatch.setattr(config, "config_path", lambda: tmp_path / "cfg" / "settings.json")
    w = MainWindow()
    w.output_panel.directory.setText(str(tmp_path / "out"))
    yield w
    w.close()


@pytest.fixture(scope="session")
def qapp():
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    yield app


def test_add_folder_and_name_preview(window, tmp_path, qapp):
    src = tmp_path / "in"
    src.mkdir()
    Image.new("RGB", (300, 200)).save(src / "beach.jpg")
    (src / "notes.txt").write_text("ignored")
    window.upscale_panel.enabled.setChecked(True)
    window.upscale_panel.scale.setCurrentIndex(window.upscale_panel.scale.findData(2))
    window.add_paths([str(src)])
    qapp.processEvents()
    assert window.files.count() == 1
    text = window.output_panel.preview.text()
    assert text.splitlines()[0] == "beach/"
    assert "beach_1x1_400x400.png" in text and "beach_16x9_600x338.png" in text


def test_template_error_shown(window, qapp):
    window.output_panel.file_template.setText("{name}_{nope}")
    qapp.processEvents()
    assert "nope" in window.output_panel.preview.text()


def test_ratio_rows_roundtrip(window, qapp):
    from imagesizer.config import RatioSpec

    specs = [RatioSpec("4:5", size_mode="exact", width=1080, height=1350), RatioSpec("21:9", enabled=False)]
    window.ratio_panel.load(specs)
    assert window.ratio_panel.specs() == specs


def test_resize_only_run(window, tmp_path, qapp):
    from PySide6.QtCore import QEventLoop, QTimer

    Image.new("RGB", (300, 200), "red").save(tmp_path / "a.png")
    window.upscale_panel.enabled.setChecked(False)
    window.add_paths([str(tmp_path / "a.png")])
    window._run()
    loop = QEventLoop()
    window.worker.finished.connect(loop.quit)
    QTimer.singleShot(20000, loop.quit)
    loop.exec()
    qapp.processEvents()
    outs = sorted(p.name for p in (tmp_path / "out" / "a").iterdir())
    assert outs == ["a_16x9_300x169.png", "a_1x1_200x200.png", "a_4x5_160x200.png"]
    assert window.status.text().startswith("Finished")
