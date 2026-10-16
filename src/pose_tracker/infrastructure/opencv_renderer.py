from __future__ import annotations

import cv2
import numpy as np

from pose_tracker.domain.pose import SKELETON, Landmark, Pose
from collections.abc import Sequence

_BONE_COLOR = (0, 255, 0)
_JOINT_COLOR = (0, 0, 255)
_TEXT_COLOR = (255, 255, 255)


class OpenCvPoseRenderer:
    def __init__(self, visibility_threshold: float, show_fps: bool = True) -> None:
        self._threshold = visibility_threshold
        self._show_fps = show_fps

    def render(
        self,
        image: np.ndarray,
        pose: Pose | None,
        fps: float,
        status_lines: Sequence[str] = (),
    ) -> np.ndarray:
        canvas = image.copy()
        if pose is not None:
            self._draw_pose(canvas, pose)
        if self._show_fps:
            self._draw_text(canvas, f"FPS: {fps:.1f}", y=30)
        for index, line in enumerate(status_lines):
            self._draw_text(canvas, line, y=65 + index * 32)
        return canvas

    @staticmethod
    def _draw_text(canvas: np.ndarray, text: str, y: int) -> None:
        origin = (10, y)
        font = cv2.FONT_HERSHEY_SIMPLEX
        cv2.putText(canvas, text, origin, font, 0.8, (0, 0, 0), 4, cv2.LINE_AA)  # outline
        cv2.putText(canvas, text, origin, font, 0.8, _TEXT_COLOR, 2, cv2.LINE_AA)
    def _draw_pose(self, canvas: np.ndarray, pose: Pose) -> None:
        height, width = canvas.shape[:2]
        for start_id, end_id in SKELETON:
            start, end = pose.get(start_id), pose.get(end_id)
            if self._is_visible(start) and self._is_visible(end):
                cv2.line(
                    canvas,
                    self._to_pixel(start, width, height),
                    self._to_pixel(end, width, height),
                    _BONE_COLOR, 2, cv2.LINE_AA,
                )
        for landmark in pose.landmarks:
            if self._is_visible(landmark):
                cv2.circle(
                    canvas, self._to_pixel(landmark, width, height),
                    4, _JOINT_COLOR, -1, cv2.LINE_AA,
                )

    def _is_visible(self, landmark: Landmark) -> bool:
        return landmark.visibility >= self._threshold

    @staticmethod
    def _to_pixel(landmark: Landmark, width: int, height: int) -> tuple[int, int]:
        return int(landmark.x * width), int(landmark.y * height)