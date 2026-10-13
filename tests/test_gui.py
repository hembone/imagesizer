"""Offscreen GUI checks: window builds, inputs load, name preview and run/validation wiring."""

import gc
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
    if w.worker is not None:
        w.worker.cancel.set()
        w.worker.wait()
    # Tear the window down here rather than whenever a later test happens to trigger garbage collection.
    w.deleteLater()
    QtWidgets.QApplication.sendPostedEvents(None, 0)
    qapp.processEvents()
    gc.collect()


@pytest.fixture(scope="session")
def qapp():
    from imagesizer.gui import theme

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    theme.apply(app)  # build every test window under the real stylesheet
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


@pytest.mark.parametrize("ready,dismissed,answer,expect_ask,expect_download", [
    (True, False, True, False, False),    # engine installed: never ask
    (False, True, True, False, False),    # user said "Later" before: don't nag
    (False, False, True, True, True),     # first run, accepts
    (False, False, False, True, False),   # first run, declines
])
def test_first_run_engine_prompt(window, tmp_path, monkeypatch, ready, dismissed, answer, expect_ask,
                                 expect_download):
    from imagesizer import config
    from imagesizer.engine.upscayl import Engine

    window.engine = Engine(tmp_path / "bin", tmp_path / "models")
    if ready:
        window.engine.binary.touch()
        window.engine.models_dir.mkdir()
        for ext in ("param", "bin"):
            (window.engine.models_dir / f"m.{ext}").touch()
    window.settings.engine_prompt_dismissed = dismissed
    asked, downloaded = [], []
    monkeypatch.setattr(window, "_ask_engine_download", lambda: asked.append(1) or answer)
    monkeypatch.setattr(window, "_download_engine", lambda: downloaded.append(1))
    window.offer_engine_download()
    assert bool(asked) == expect_ask
    assert bool(downloaded) == expect_download
    if expect_ask and not answer:
        assert config.load().engine_prompt_dismissed  # remembered across launches


def test_window_title_has_version(window):
    from imagesizer import __version__

    assert window.windowTitle() == f"ImageSizer {__version__}" and __version__ != "dev"


def test_list_thumbnails_load(window, tmp_path, qapp):
    from imagesizer.gui.main_window import THUMB_ROLE

    Image.new("RGB", (300, 200), "blue").save(tmp_path / "a.png")
    Image.new("RGB", (100, 400), "green").save(tmp_path / "b.jpg")
    window.add_paths([str(tmp_path / "a.png"), str(tmp_path / "b.jpg")])
    for _ in range(10):
        qapp.processEvents()
    for i in range(window.files.count()):
        thumb = window.files.item(i).data(THUMB_ROLE)
        assert thumb is not None and not thumb.isNull()
    window._clear()
    assert window._thumb_row == 0 and not window._thumb_timer.isActive()


def test_file_list_locked_while_running(window, tmp_path, qapp):
    from PySide6.QtCore import QEventLoop, QTimer

    Image.new("RGB", (60, 40)).save(tmp_path / "a.png")
    window.upscale_panel.enabled.setChecked(False)
    window.add_paths([str(tmp_path / "a.png")])
    window._run()
    assert window.files.locked
    assert not any(b.isEnabled() for b in (*window.file_buttons, *window.preset_controls))
    window.add_paths([str(tmp_path / "a.png"), str(tmp_path)])  # e.g. a drop: ignored mid-run
    assert window.files.count() == 1
    loop = QEventLoop()
    window.worker.finished.connect(loop.quit)
    QTimer.singleShot(20000, loop.quit)
    loop.exec()
    qapp.processEvents()
    assert not window.files.locked and all(b.isEnabled() for b in window.file_buttons)
