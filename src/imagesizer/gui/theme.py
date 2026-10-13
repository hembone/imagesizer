"""Dark theme: palette, app-wide stylesheet and a few painting helpers shared by the panels."""

from __future__ import annotations

from importlib.resources import files

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QFont, QIcon, QPainter, QPalette, QPixmap
from PySide6.QtWidgets import QAbstractSpinBox, QApplication, QLineEdit, QWidget

BG = "#15171c"
SURFACE = "#1d2027"
SURFACE_2 = "#272b34"
SURFACE_3 = "#323743"
BORDER = "#333845"
TEXT = "#e7e9ee"
MUTED = "#9aa1ad"
DISABLED = "#5c626e"
ACCENT = "#7b6cff"
ACCENT_HOVER = "#8d80ff"
ACCENT_PRESSED = "#6a5ae8"
ERROR = "#ff6b6b"
OK = "#4cc38a"

_RES = str(files("imagesizer") / "resources").replace("\\", "/")  # QSS url() wants forward slashes

STYLESHEET = f"""
QMainWindow, QDialog {{ background: {BG}; }}
QWidget {{ color: {TEXT}; }}
QToolTip {{ background: {SURFACE_2}; color: {TEXT}; border: 1px solid {BORDER}; border-radius: 6px; padding: 4px 6px; }}

QGroupBox {{
    background: {SURFACE}; border: 1px solid {BORDER}; border-radius: 10px;
    margin-top: 0; padding: 34px 12px 10px 12px; font-weight: 600;
}}
QGroupBox::title {{
    subcontrol-origin: padding; subcontrol-position: top left; left: 14px; top: 10px; color: {TEXT};
}}
QGroupBox QWidget {{ font-weight: normal; }}

QLabel#sectionTitle {{ color: {MUTED}; font-weight: 600; }}
QLabel#muted {{ color: {MUTED}; }}
QLabel#codeBlock {{ background: {BG}; border: 1px solid {BORDER}; border-radius: 6px; padding: 8px; }}
QLabel[state="ok"] {{ color: {OK}; }}
QLabel[state="off"] {{ color: {MUTED}; }}

QPushButton, QToolButton {{
    background: {SURFACE_2}; border: 1px solid {BORDER}; border-radius: 6px; padding: 5px 12px;
}}
QPushButton:hover, QToolButton:hover {{ background: {SURFACE_3}; }}
QPushButton:pressed, QToolButton:pressed {{ background: {BORDER}; }}
QPushButton:disabled, QToolButton:disabled {{ color: {DISABLED}; background: {SURFACE}; }}
QToolButton {{ padding: 2px; }}
QToolButton:checked {{ background: {ACCENT}; border-color: {ACCENT}; color: white; }}
QToolButton[flat="true"] {{ background: transparent; border: none; color: {MUTED}; }}
QToolButton[flat="true"]:hover {{ color: {ERROR}; }}
QPushButton[primary="true"] {{
    background: {ACCENT}; border: 1px solid {ACCENT}; color: white; font-weight: 600; padding: 8px 22px;
}}
QPushButton[primary="true"]:hover {{ background: {ACCENT_HOVER}; }}
QPushButton[primary="true"]:pressed {{ background: {ACCENT_PRESSED}; }}
QPushButton[primary="true"]:disabled {{ background: {SURFACE_2}; border-color: {BORDER}; color: {DISABLED}; }}

QLineEdit, QComboBox, QSpinBox {{
    background: {BG}; border: 1px solid {BORDER}; border-radius: 6px; padding: 4px 8px; min-height: 20px;
    selection-background-color: {ACCENT};
}}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus {{ border-color: {ACCENT}; }}
QLineEdit:disabled, QComboBox:disabled, QSpinBox:disabled {{ color: {DISABLED}; }}
QSpinBox {{ padding-right: 22px; }}
QSpinBox::up-button, QSpinBox::down-button {{
    subcontrol-origin: border; width: 20px; border: none; border-left: 1px solid {BORDER}; background: {SURFACE_2};
}}
QSpinBox::up-button {{ subcontrol-position: top right; border-top-right-radius: 6px; }}
QSpinBox::down-button {{ subcontrol-position: bottom right; border-bottom-right-radius: 6px; }}
QSpinBox::up-button:hover, QSpinBox::down-button:hover {{ background: {SURFACE_3}; }}
QSpinBox::up-arrow {{ image: url({_RES}/arrow-up.svg); width: 9px; height: 6px; }}
QSpinBox::down-arrow {{ image: url({_RES}/arrow-down.svg); width: 9px; height: 6px; }}
QSpinBox::up-arrow:disabled {{ image: url({_RES}/arrow-up-disabled.svg); }}
QSpinBox::down-arrow:disabled {{ image: url({_RES}/arrow-down-disabled.svg); }}
QComboBox {{ padding-right: 26px; }}
QComboBox::drop-down {{
    subcontrol-origin: padding; subcontrol-position: center right; width: 24px; border: none; background: transparent;
}}
QComboBox::down-arrow {{ image: url({_RES}/arrow-down.svg); width: 9px; height: 6px; }}
QComboBox::down-arrow:disabled {{ image: url({_RES}/arrow-down-disabled.svg); }}
QComboBox QAbstractItemView {{
    background: {SURFACE_2}; border: 1px solid {BORDER}; selection-background-color: {ACCENT}; outline: 0;
}}

QListWidget {{ background: {BG}; border: 1px solid {BORDER}; border-radius: 10px; padding: 4px; outline: 0; }}
QListWidget::item {{ padding: 4px; border-radius: 6px; }}
QListWidget::item:hover {{ background: {SURFACE}; }}
QListWidget::item:selected {{ background: #3a3470; color: {TEXT}; }}

QProgressBar {{ background: {SURFACE_2}; border: none; border-radius: 4px; max-height: 8px; min-height: 8px; }}
QProgressBar::chunk {{ background: {ACCENT}; border-radius: 4px; }}

QScrollArea {{ border: none; background: transparent; }}
QScrollArea > QWidget > QWidget {{ background: transparent; }}
QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px; }}
QScrollBar:horizontal {{ background: transparent; height: 10px; margin: 2px; }}
QScrollBar::handle {{ background: {SURFACE_3}; border-radius: 3px; min-height: 24px; min-width: 24px; }}
QScrollBar::handle:hover {{ background: {MUTED}; }}
QScrollBar::add-line, QScrollBar::sub-line {{ width: 0; height: 0; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: none; }}

QSplitter::handle {{ background: transparent; width: 8px; }}
QWidget#runBar {{ background: {SURFACE}; border-top: 1px solid {BORDER}; }}
"""


def palette() -> QPalette:
    p = QPalette()
    roles = {
        QPalette.ColorRole.Window: BG, QPalette.ColorRole.WindowText: TEXT,
        QPalette.ColorRole.Base: BG, QPalette.ColorRole.AlternateBase: SURFACE,
        QPalette.ColorRole.Text: TEXT, QPalette.ColorRole.Button: SURFACE_2,
        QPalette.ColorRole.ButtonText: TEXT, QPalette.ColorRole.BrightText: "#ffffff",
        QPalette.ColorRole.Highlight: ACCENT, QPalette.ColorRole.HighlightedText: "#ffffff",
        QPalette.ColorRole.ToolTipBase: SURFACE_2, QPalette.ColorRole.ToolTipText: TEXT,
        QPalette.ColorRole.PlaceholderText: MUTED, QPalette.ColorRole.Link: ACCENT_HOVER,
        QPalette.ColorRole.Light: SURFACE_3, QPalette.ColorRole.Midlight: SURFACE_2,
        QPalette.ColorRole.Mid: BORDER, QPalette.ColorRole.Dark: BG, QPalette.ColorRole.Shadow: "#000000",
    }
    for role, color in roles.items():
        p.setColor(role, QColor(color))
    for role in (QPalette.ColorRole.WindowText, QPalette.ColorRole.Text, QPalette.ColorRole.ButtonText):
        p.setColor(QPalette.ColorGroup.Disabled, role, QColor(DISABLED))
    return p


def apply(app: QApplication) -> None:
    app.setStyle("Fusion")  # same look on Linux, Windows and macOS
    app.setPalette(palette())
    app.setStyleSheet(STYLESHEET)


def set_state(widget: QWidget, name: str, value) -> None:
    """Set a dynamic property the stylesheet keys on and re-polish so the change shows."""
    widget.setProperty(name, value)
    widget.style().unpolish(widget)
    widget.style().polish(widget)


def spin_box(box: QAbstractSpinBox) -> QAbstractSpinBox:
    """Inset the text like the other inputs; spin boxes ignore QSS left padding."""
    box.findChild(QLineEdit).setTextMargins(8, 0, 0, 0)
    return box


def badge(pixmap: QPixmap, color: str, glyph: str) -> QPixmap:
    """Copy of a thumbnail with a small round status badge in the bottom-right corner."""
    out = QPixmap(pixmap)
    p = QPainter(out)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    d = max(12, out.width() * 0.45)
    r = QRectF(out.width() - d, out.height() - d, d, d)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor(BG))
    p.drawEllipse(r)
    p.setBrush(QColor(color))
    p.drawEllipse(r.adjusted(1.5, 1.5, -1.5, -1.5))
    font = QFont()
    font.setBold(True)
    font.setPixelSize(round(d * 0.6))
    p.setFont(font)
    p.setPen(QColor(BG))
    p.drawText(r, Qt.AlignmentFlag.AlignCenter, glyph)
    p.end()
    return out


def icon(pixmap: QPixmap) -> QIcon:
    """Icon that looks the same when its row is selected (Qt tints Selected-mode icons otherwise)."""
    ic = QIcon(pixmap)
    ic.addPixmap(pixmap, QIcon.Mode.Selected)
    return ic
