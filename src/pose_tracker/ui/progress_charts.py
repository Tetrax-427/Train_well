from __future__ import annotations

import math
from collections.abc import Sequence

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import QScrollArea, QWidget

from pose_tracker.application.progress_layout import (
    BAR_GAP,
    DAY_GAP,
    LEFT_MARGIN,
    ChartLayout,
    compute_layout,
    nice_axis,
)
from pose_tracker.domain.progress import DayProgress, ProgressChartData, format_value

_BACKGROUND = QColor("#0d1117")
_GRID = QColor("#30363d")
_MUTED = QColor("#8b949e")
_TEXT = QColor("#e6edf3")

PANEL_HEIGHT = 230
PANEL_SPACING = 10
_TITLE_BAND = 34
_DATE_BAND = 26

Values = tuple[tuple[float, ...], ...]  # per day: one value per set (bars) or one value (line)


class _Panel(QWidget):
    """One chart. The y-axis labels and title stay pinned to the left edge while scrolling."""

    def __init__(self, color: str, line: bool) -> None:
        super().__init__()
        self._color = QColor(color)
        self._line = line
        self._title = ""
        self._days: tuple[DayProgress, ...] = ()
        self._chart_layout: ChartLayout | None = None
        self._values: Values = ()
        self._offset = 0
        self.setFixedHeight(PANEL_HEIGHT)

    def set_content(
        self, title: str, days: tuple[DayProgress, ...], chart_layout: ChartLayout, values: Values
    ) -> None:
        self._title, self._days = title, days
        self._chart_layout, self._values = chart_layout, values
        self.update()

    def set_offset(self, offset: int) -> None:
        self._offset = offset
        self.update()

    def paintEvent(self, event: object) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), _BACKGROUND)
        if self._chart_layout is None or not self._values:
            return
        font = QFont(self.font())
        font.setPixelSize(11)
        painter.setFont(font)

        plot = QRectF(
            LEFT_MARGIN, _TITLE_BAND,
            self.width() - LEFT_MARGIN, self.height() - _TITLE_BAND - _DATE_BAND,
        )
        axis_max, step = nice_axis(max(value for day in self._values for value in day))
        ticks = [i * step for i in range(round(axis_max / step) + 1)]

        painter.setPen(QPen(_GRID, 1))
        for tick in ticks:
            y = plot.bottom() - plot.height() * tick / axis_max
            painter.drawLine(QPointF(LEFT_MARGIN, y), QPointF(self.width(), y))

        if self._line:
            self._paint_line(painter, plot, axis_max)
        else:
            self._paint_bars(painter, plot, axis_max)
        self._paint_dates(painter, plot)
        self._paint_pinned(painter, plot, axis_max, ticks)

    def _paint_bars(self, painter: QPainter, plot: QRectF, axis_max: float) -> None:
        layout = self._chart_layout
        assert layout is not None
        for slot, values in zip(layout.slots, self._values, strict=True):
            for index, value in enumerate(values):
                left = slot.bars_left + index * (layout.bar_width + BAR_GAP)
                height = plot.height() * value / axis_max
                top = plot.bottom() - height
                if value > 0:
                    painter.setPen(Qt.PenStyle.NoPen)
                    painter.setBrush(self._color)
                    painter.drawRoundedRect(
                        QRectF(left, top, layout.bar_width, max(height, 2.0)), 3, 3
                    )
                self._paint_value(painter, format_value(value), left + layout.bar_width / 2, top)

    def _paint_line(self, painter: QPainter, plot: QRectF, axis_max: float) -> None:
        layout = self._chart_layout
        assert layout is not None
        points = [
            QPointF(slot.center, plot.bottom() - plot.height() * values[0] / axis_max)
            for slot, values in zip(layout.slots, self._values, strict=True)
        ]
        painter.setPen(QPen(self._color, 2.5))
        for first, second in zip(points, points[1:]):
            painter.drawLine(first, second)
        painter.setBrush(self._color)
        for point, values in zip(points, self._values, strict=True):
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(point, 4.5, 4.5)
            self._paint_value(painter, format_value(values[0]), point.x(), point.y() - 6)

    @staticmethod
    def _paint_value(painter: QPainter, text: str, center_x: float, bottom: float) -> None:
        painter.setPen(_TEXT)
        painter.drawText(
            QRectF(center_x - 30, bottom - 18, 60, 16), Qt.AlignmentFlag.AlignCenter, text
        )

    def _paint_dates(self, painter: QPainter, plot: QRectF) -> None:
        layout = self._chart_layout
        assert layout is not None
        painter.setPen(_MUTED)
        for slot, day in zip(layout.slots, self._days, strict=True):
            rect = QRectF(slot.left - DAY_GAP / 2, plot.bottom() + 6, slot.width + DAY_GAP, 16)
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, f"{day.day:%d %b}")

    def _paint_pinned(
        self, painter: QPainter, plot: QRectF, axis_max: float, ticks: Sequence[float]
    ) -> None:
        painter.fillRect(QRectF(self._offset, 0, LEFT_MARGIN, self.height()), _BACKGROUND)
        painter.setPen(_MUTED)
        for tick in ticks:
            y = plot.bottom() - plot.height() * tick / axis_max
            painter.drawText(
                QRectF(self._offset, y - 8, LEFT_MARGIN - 8, 16),
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                format_value(tick),
            )
        bold = QFont(painter.font())
        bold.setBold(True)
        bold.setPixelSize(13)
        painter.setFont(bold)
        painter.setPen(_TEXT)
        painter.drawText(
            QRectF(self._offset + 8, 8, 420, 20),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            self._title,
        )


class ProgressCharts(QScrollArea):
    """Reps, weight and volume charts that share one set of day columns and scroll together."""

    def __init__(self) -> None:
        super().__init__()
        self.setWidgetResizable(False)
        self._content = QWidget()
        self.setWidget(self._content)
        self._reps = _Panel("#1f6feb", line=False)
        self._weights = _Panel("#d29922", line=False)
        self._volume = _Panel("#3fb950", line=True)
        for panel in (self._reps, self._weights, self._volume):
            panel.setParent(self._content)
        self._data: ProgressChartData | None = None
        self.horizontalScrollBar().valueChanged.connect(self._on_scrolled)

    def show_data(self, data: ProgressChartData) -> None:
        self._data = data
        self._rebuild()

    def resizeEvent(self, event: object) -> None:
        super().resizeEvent(event)
        self._rebuild()

    def _rebuild(self) -> None:
        data = self._data
        if data is None or not data.days:
            return
        viewport = self.viewport().width()
        usable = max(viewport - self.verticalScrollBar().sizeHint().width(), 1)
        chart_layout = compute_layout([len(day.sets) for day in data.days], usable)
        width = max(viewport, math.ceil(chart_layout.total_width))

        specs = (
            (self._reps, "Reps per set", tuple(day.reps for day in data.days), True),
            (
                self._weights, "Weight per set (kg)",
                tuple(day.weights for day in data.days), data.has_weights,
            ),
            (
                self._volume, f"Training volume ({data.volume_unit})",
                tuple((volume,) for volume in data.volumes), True,
            ),
        )
        y = PANEL_SPACING
        for panel, title, values, visible in specs:
            panel.setVisible(visible)
            if not visible:
                continue
            panel.set_content(title, data.days, chart_layout, values)
            panel.setGeometry(0, y, width, PANEL_HEIGHT)
            y += PANEL_HEIGHT + PANEL_SPACING
        self._content.setFixedSize(width, y)
        self._on_scrolled(self.horizontalScrollBar().value())

    def _on_scrolled(self, value: int) -> None:
        for panel in (self._reps, self._weights, self._volume):
            panel.set_offset(value)