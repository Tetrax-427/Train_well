from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout

from pose_tracker.application.history_presenter import MistakeCardData
from pose_tracker.interfaces import SnapshotPainter
from pose_tracker.ui.qt_helpers import to_qimage

_PHOTO_WIDTH = 360


def _swatch(color: str, text: str) -> str:
    return f'<span style="color:{color}">■</span> {text}'


# Colors match the painter: green (0,200,0), red (255,0,0), purple (170,60,230) in RGB.
_GREEN = _swatch("#00c800", "your pose")
_RED = _swatch("#ff0000", "joints at fault")
_PURPLE = _swatch("#00E5FF", "corrected pose")
_NO_GHOST = "No corrected pose for this kind of mistake"


class MistakeCard(QFrame):
    """One mistake: your own snapshot, with the corrected pose, beside what was wrong and why."""

    def __init__(
        self, data: MistakeCardData, painter: SnapshotPainter, overlay: bool, show_ghost: bool
    ) -> None:
        super().__init__()
        self.setObjectName("card")
        self._data = data
        self._painter = painter

        self._photo = QLabel()
        self._photo.setFixedWidth(_PHOTO_WIDTH)
        self._photo.setMinimumHeight(180)
        self._photo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._photo.setWordWrap(True)
        self._photo.setStyleSheet("background: #010409; border-radius: 6px; color: #8b949e;")

        self._legend = QLabel()
        self._legend.setObjectName("caption")
        self._legend.setTextFormat(Qt.TextFormat.RichText)
        self._legend.setWordWrap(True)
        self._legend.setFixedWidth(_PHOTO_WIDTH)

        title = QLabel(data.title)
        title.setObjectName("cardTitle")
        title.setWordWrap(True)
        meta = QLabel(data.meta)
        meta.setObjectName("caption")
        measurement = QLabel(data.measurement)
        measurement.setObjectName("subtitle")
        measurement.setWordWrap(True)
        why = QLabel(data.explanation)
        why.setWordWrap(True)
        why.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)

        photo_column = QVBoxLayout()
        photo_column.addWidget(self._photo)
        photo_column.addWidget(self._legend)
        photo_column.addStretch(1)

        text = QVBoxLayout()
        for widget in (title, meta, measurement, why):
            text.addWidget(widget)
        text.addStretch(1)

        layout = QHBoxLayout(self)
        layout.addLayout(photo_column)
        layout.addLayout(text, 1)
        self.set_display(overlay, show_ghost)

    def set_display(self, overlay: bool, show_ghost: bool) -> None:
        data = self._data
        self._legend.setText(self._legend_html(overlay, show_ghost))
        if data.snapshot_path is None:
            self._show_message("No snapshot was saved for this mistake")
            return
        image = self._painter.paint(
            data.snapshot_path,
            data.pose,
            data.highlights,
            overlay,
            data.ghost if show_ghost else None,
        )
        if image is None:
            self._show_message("The snapshot file could not be read")
            return
        pixmap = QPixmap.fromImage(to_qimage(image)).scaledToWidth(
            _PHOTO_WIDTH, Qt.TransformationMode.SmoothTransformation
        )
        self._photo.setPixmap(pixmap)

    def _legend_html(self, overlay: bool, show_ghost: bool) -> str:
        entries = [_GREEN, _RED] if overlay else []
        if self._data.ghost is None:
            entries.append(_NO_GHOST)
        elif show_ghost:
            entries.append(_PURPLE)
        return " &nbsp;&nbsp; ".join(entries)

    def _show_message(self, message: str) -> None:
        self._photo.setPixmap(QPixmap())
        self._photo.setText(message)