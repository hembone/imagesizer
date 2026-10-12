import sys


def main() -> int:
    from PySide6.QtWidgets import QApplication

    from .gui.main_window import MainWindow

    app = QApplication(sys.argv)
    app.setApplicationName("ImageSizer")
    app.setOrganizationName("imagesizer")
    app.setStyle("Fusion")  # same look on Linux, Windows and macOS
    win = MainWindow()
    win.add_paths(sys.argv[1:])
    win.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
