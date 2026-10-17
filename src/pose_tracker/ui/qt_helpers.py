from __future__ import annotations

import numpy as np
from PySide6.QtGui import QImage
from PySide6.QtWidgets import QLayout


def to_qimage(image: np.ndarray) -> QImage:
    """A BGR numpy image as a QImage that owns its pixels."""
    frame = np.ascontiguousarray(image)
    height, width = frame.shape[:2]
    return QImage(
        frame.data, width, height, frame.strides[0], QImage.Format.Format_BGR888
    ).copy()


def clear_layout(layout: QLayout) -> None:
    while (item := layout.takeAt(0)) is not None:
        if (widget := item.widget()) is not None:
            widget.deleteLater()