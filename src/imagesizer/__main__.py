import sys
from importlib.resources import files


def main() -> int:
    from PySide6.QtCore import QTimer
    from PySide6.QtGui import QIcon
    from PySide6.QtWidgets import QApplication

    from .gui import theme
    from .gui.main_window import MainWindow

    app = QApplication(sys.argv)
    app.setApplicationName("ImageSizer")
    app.setOrganizationName("imagesizer")
    theme.apply(app)
    app.setWindowIcon(QIcon(str(files("imagesizer") / "resources" / "icon.png")))
    app.setDesktopFileName("imagesizer")  # matches the .desktop entry so Linux docks show the right icon
    win = MainWindow()
    win.add_paths(sys.argv[1:])
    win.show()
    QTimer.singleShot(0, win.offer_engine_download)
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
