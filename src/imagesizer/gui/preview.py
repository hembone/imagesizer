"""Thumbnail with the crop region (or padded canvas) drawn for one ratio."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QRectF, QSize, Qt
from PySide6.QtGui import QBrush, QColor, QImage, QImageIOHandler, QImageReader, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import QSizePolicy, QWidget

from ..processing.ratios import Ratio
from ..processing.resize import crop_box, pad_layout
from . import theme

THUMB_MAX = 1200
CHECKER = 8


def _checkerboard() -> QPixmap:
    pm = QPixmap(CHECKER * 2, CHECKER * 2)
    pm.fill(QColor("#cfd2d8"))
    p = QPainter(pm)
    p.fillRect(0, 0, CHECKER, CHECKER, QColor("#a9adb5"))
    p.fillRect(CHECKER, CHECKER, CHECKER, CHECKER, QColor("#a9adb5"))
    p.end()
    return pm


class PreviewWidget(QWidget):
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setMinimumSize(240, 180)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.image: QImage | None = None
        self.source_size: tuple[int, int] = (0, 0)
        self.ratio: Ratio | None = None
        self.fit_mode = "crop"
        self.anchor = "center"
        self.pad_color: QColor | None = QColor("#ffffff")
        self.message = "Add images to see a preview"

    def sizeHint(self) -> QSize:
        return QSize(360, 270)

    def set_image(self, path: Path | None) -> None:
        self.image = None
        if path is not None:
            reader = QImageReader(str(path))
            reader.setAutoTransform(True)  # honor EXIF orientation like the pipeline does
            size = reader.size()  # stored (pre-rotation) size, read from the header without decoding
            if size.isValid() and max(size.width(), size.height()) > THUMB_MAX:
                # decode straight to preview size; JPEG in particular skips most of the work this way
                reader.setScaledSize(size.scaled(THUMB_MAX, THUMB_MAX, Qt.AspectRatioMode.KeepAspectRatio))
            img = reader.read()
            if img.isNull():
                self.message = f"Cannot preview: {reader.errorString()}"
            else:
                if size.isValid():
                    rotated = bool(reader.transformation() & QImageIOHandler.Transformation.TransformationRotate90)
                    self.source_size = (size.height(), size.width()) if rotated else (size.width(), size.height())
                else:
                    self.source_size = (img.width(), img.height())
                if max(img.width(), img.height()) > THUMB_MAX:
                    img = img.scaled(THUMB_MAX, THUMB_MAX, Qt.AspectRatioMode.KeepAspectRatio,
                                     Qt.TransformationMode.SmoothTransformation)
                self.image = img
        else:
            self.message = "Add images to see a preview"
        self.update()

    def set_overlay(self, ratio: Ratio | None, fit_mode: str, anchor: str, pad_color: QColor | None) -> None:
        self.ratio, self.fit_mode, self.anchor, self.pad_color = ratio, fit_mode, anchor, pad_color
        self.update()

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHints(QPainter.RenderHint.SmoothPixmapTransform | QPainter.RenderHint.Antialiasing)
        panel = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        clip = QPainterPath()
        clip.addRoundedRect(panel, 10, 10)
        p.fillPath(clip, QColor(theme.BG))
        p.setPen(QPen(QColor(theme.BORDER), 1))
        p.drawPath(clip)
        p.setClipPath(clip)
        if self.image is None:
            p.setPen(QColor(theme.MUTED))
            p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap, self.message)
            return
        iw, ih = self.image.width(), self.image.height()
        if self.ratio is not None and self.fit_mode == "pad":
            cw, ch, ox, oy = pad_layout(iw, ih, self.ratio, self.anchor)
        else:
            cw, ch, ox, oy = iw, ih, 0, 0
        scale = min((self.width() - 32) / cw, (self.height() - 32) / ch)
        x0 = (self.width() - cw * scale) / 2
        y0 = (self.height() - ch * scale) / 2
        canvas = QRectF(x0, y0, cw * scale, ch * scale)
        img_rect = QRectF(x0 + ox * scale, y0 + oy * scale, iw * scale, ih * scale)

        if self.ratio is not None and self.fit_mode == "pad":
            if self.pad_color is None:  # transparent: checkerboard
                p.fillRect(canvas, QBrush(_checkerboard()))
            else:
                p.fillRect(canvas, self.pad_color)
        p.drawImage(img_rect, self.image)

        if self.ratio is None:
            return
        pen = QPen(QColor(theme.ACCENT), 2)
        if self.fit_mode == "crop":
            left, top, right, bottom = crop_box(iw, ih, self.ratio, self.anchor)
            box = QRectF(img_rect.x() + left * scale, img_rect.y() + top * scale,
                         (right - left) * scale, (bottom - top) * scale)
            shade = QColor(0, 0, 0, 140)
            p.fillRect(QRectF(img_rect.left(), img_rect.top(), img_rect.width(), box.top() - img_rect.top()), shade)
            p.fillRect(QRectF(img_rect.left(), box.bottom(), img_rect.width(), img_rect.bottom() - box.bottom()), shade)
            p.fillRect(QRectF(img_rect.left(), box.top(), box.left() - img_rect.left(), box.height()), shade)
            p.fillRect(QRectF(box.right(), box.top(), img_rect.right() - box.right(), box.height()), shade)
            p.setPen(pen)
            p.drawRect(box)
        else:
            p.setPen(pen)
            p.drawRect(canvas)
