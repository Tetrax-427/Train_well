from __future__ import annotations

import logging
import threading
from dataclasses import dataclass

from PySide6.QtCore import QObject, QThread, Signal

from pose_tracker.domain.frame import Frame
from pose_tracker.domain.pose import Pose
from pose_tracker.interfaces import FrameSource, PoseEstimator

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class CapturedFrame:
    frame: Frame
    pose: Pose | None


class CaptureThread(QThread):
    """Reads the camera and runs pose estimation off the UI thread.

    Every frame is estimated (so tracking stays continuous), but a frame is only handed
    to the UI when it has finished with the previous one; otherwise it is dropped.
    """

    frame_ready = Signal(object)  # CapturedFrame
    stopped = Signal(str)  # empty = stopped on request, otherwise the failure reason

    def __init__(
        self, source: FrameSource, estimator: PoseEstimator, parent: QObject | None = None
    ) -> None:
        super().__init__(parent)
        self._source = source
        self._estimator = estimator
        self._stop_requested = threading.Event()
        self._ui_busy = threading.Event()

    def run(self) -> None:
        reason = ""
        try:
            while not self._stop_requested.is_set():
                frame = self._source.read()
                if frame is None:
                    reason = "The camera stopped delivering frames."
                    break
                pose = self._estimator.estimate(frame)
                if self._ui_busy.is_set():
                    continue
                self._ui_busy.set()
                self.frame_ready.emit(CapturedFrame(frame, pose))
        except Exception:  # thread boundary: report to the UI instead of dying silently
            logger.exception("Capture loop crashed")
            reason = "The capture loop failed unexpectedly. See the log for details."
        self.stopped.emit(reason)

    def request_stop(self) -> None:
        self._stop_requested.set()

    def frame_consumed(self) -> None:
        """The UI calls this when it has finished with the last emitted frame."""
        self._ui_busy.clear()