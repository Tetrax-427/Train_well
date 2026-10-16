from __future__ import annotations

import numpy as np
from PySide6.QtCore import QRect, Qt
from PySide6.QtGui import QColor, QImage, QPainter
from PySide6.QtWidgets import QSizePolicy, QWidget


class VideoWidget(QWidget):
    """Shows BGR frames scaled to fit, keeping the aspect ratio."""

    def __init__(self, placeholder: str = "Starting camera…") -> None:
        super().__init__()
        self._placeholder = placeholder
        self._image: QImage | None = None
        self.setMinimumSize(480, 270)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    def show_image(self, image: np.ndarray) -> None:
        frame = np.ascontiguousarray(image)
        height, width = frame.shape[:2]
        # copy() so the QImage owns its pixels once the numpy buffer is gone
        self._image = QImage(
            frame.data, width, height, frame.strides[0], QImage.Format.Format_BGR888
        ).copy()
        self.update()

    def paintEvent(self, event: object) -> None:
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor("#010409"))
        if self._image is None:
            painter.setPen(QColor("#8b949e"))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, self._placeholder)
            return
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        size = self._image.size().scaled(self.size(), Qt.AspectRatioMode.KeepAspectRatio)
        x = (self.width() - size.width()) // 2
        y = (self.height() - size.height()) // 2
        painter.drawImage(QRect(x, y, size.width(), size.height()), self._image)