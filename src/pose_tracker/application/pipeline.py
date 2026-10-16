from __future__ import annotations

import logging
from collections.abc import Sequence

from pose_tracker.application.fps import FpsMeter
from pose_tracker.interfaces import (
    FrameDisplay,
    FrameObserver,
    FrameSource,
    PoseAnalyzer,
    PoseEstimator,
    PoseRenderer,
)

logger = logging.getLogger(__name__)


class PosePipeline:
    """Capture -> estimate -> analyze -> render -> display. Owns no resources."""

    def __init__(
        self,
        source: FrameSource,
        estimator: PoseEstimator,
        analyzer: PoseAnalyzer,
        renderer: PoseRenderer,
        display: FrameDisplay,
        fps_meter: FpsMeter,
        observers: Sequence[FrameObserver] = (),
    ) -> None:
        self._source = source
        self._estimator = estimator
        self._analyzer = analyzer
        self._renderer = renderer
        self._display = display
        self._fps_meter = fps_meter
        self._observers = tuple(observers)

    def run(self) -> None:
        logger.info("Pipeline started")
        while True:
            frame = self._source.read()
            if frame is None:
                logger.warning("Frame source ended or failed; stopping")
                return
            for observer in self._observers:
                observer.observe(frame)  # before analysis, so a finished rep can find its frame
            pose = self._estimator.estimate(frame)
            self._fps_meter.tick()
            height, width = frame.image.shape[:2]
            status_lines = self._analyzer.analyze(pose, frame.timestamp_ms, width / height)
            output = self._renderer.render(
                frame.image, pose, self._fps_meter.fps, status_lines
            )
            if not self._display.show(output):
                logger.info("Stop requested by user")
                return