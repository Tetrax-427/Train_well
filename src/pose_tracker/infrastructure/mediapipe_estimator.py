from __future__ import annotations

from pathlib import Path

import cv2
import mediapipe as mp
from mediapipe.tasks import python as mp_python
from mediapipe.tasks.python import vision

from pose_tracker.domain.frame import Frame
from pose_tracker.domain.pose import Landmark, Pose
from pose_tracker.errors import ModelLoadError


class MediaPipePoseEstimator:
    """Single-person pose estimation using MediaPipe PoseLandmarker (VIDEO mode, with tracking)."""

    def __init__(
        self,
        model_path: Path,
        min_detection_confidence: float,
        min_presence_confidence: float,
        min_tracking_confidence: float,
    ) -> None:
        if not model_path.is_file():
            raise ModelLoadError(f"Model file not found: {model_path}")
        options = vision.PoseLandmarkerOptions(
            base_options=mp_python.BaseOptions(model_asset_path=str(model_path)),
            running_mode=vision.RunningMode.VIDEO,
            num_poses=1,
            min_pose_detection_confidence=min_detection_confidence,
            min_pose_presence_confidence=min_presence_confidence,
            min_tracking_confidence=min_tracking_confidence,
        )
        self._landmarker = vision.PoseLandmarker.create_from_options(options)
        self._last_timestamp_ms = -1

    def estimate(self, frame: Frame) -> Pose | None:
        # MediaPipe requires strictly increasing timestamps.
        timestamp_ms = max(frame.timestamp_ms, self._last_timestamp_ms + 1)
        self._last_timestamp_ms = timestamp_ms

        rgb = cv2.cvtColor(frame.image, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
        result = self._landmarker.detect_for_video(mp_image, timestamp_ms)

        if not result.pose_landmarks:
            return None
        raw = result.pose_landmarks[0]
        return Pose(
            landmarks=tuple(
                Landmark(x=lm.x, y=lm.y, z=lm.z, visibility=lm.visibility or 0.0)
                for lm in raw
            )
        )

    def close(self) -> None:
        self._landmarker.close()