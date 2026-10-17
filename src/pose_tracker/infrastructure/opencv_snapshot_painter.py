from __future__ import annotations

import math
from collections.abc import Collection
from pathlib import Path

import cv2
import numpy as np

from pose_tracker.domain.pose import SKELETON, LandmarkId, Pose
from pose_tracker.interfaces import GhostFactory

_BONE = (0, 200, 0)
_JOINT = (255, 255, 255)
_FLAGGED = (0, 0, 255)  # BGR red
_GHOST = (255, 229, 0)  # BGR cyan
_MIN_GHOST_MOVE_PX = 3  # segments the correction leaves in place are not drawn


class OpenCvSnapshotPainter:
    """Loads a stored snapshot and draws, as asked: the corrected (ghost) pose in purple,
    then the stored pose in green with the joints at fault in red on top."""

    def __init__(self, visibility_threshold: float) -> None:
        self._threshold = visibility_threshold

    def paint(
        self,
        path: Path,
        pose: Pose,
        highlights: Collection[LandmarkId],
        overlay: bool,
        ghost: GhostFactory | None = None,
    ) -> np.ndarray | None:
        image = cv2.imread(str(path))
        if image is None:
            return None
        height, width = image.shape[:2]
        if ghost is not None and pose.landmarks:
            corrected = ghost(width / height)
            if corrected is not None:
                self._draw_ghost(image, pose, corrected)
        if overlay and pose.landmarks:
            self._draw(image, pose, frozenset(highlights))
        return image

    def _draw_ghost(self, image: np.ndarray, original: Pose, corrected: Pose) -> None:
        height, width = image.shape[:2]
        count = min(len(original.landmarks), len(corrected.landmarks))

        def pixel(pose: Pose, landmark_id: int) -> tuple[int, int]:
            landmark = pose.landmarks[landmark_id]
            return int(landmark.x * width), int(landmark.y * height)

        def shown(landmark_id: int) -> bool:
            return (
                landmark_id < count
                and corrected.landmarks[landmark_id].visibility >= self._threshold
            )

        def moved(landmark_id: int) -> bool:
            (x0, y0), (x1, y1) = pixel(original, landmark_id), pixel(corrected, landmark_id)
            return math.hypot(x1 - x0, y1 - y0) > _MIN_GHOST_MOVE_PX

        for start, end in SKELETON:
            if shown(start) and shown(end) and (moved(start) or moved(end)):
                cv2.line(
                    image, pixel(corrected, start), pixel(corrected, end), _GHOST, 4, cv2.LINE_AA
                )
        for landmark_id in LandmarkId:
            if shown(landmark_id) and moved(landmark_id):
                cv2.circle(image, pixel(corrected, landmark_id), 6, _GHOST, -1, cv2.LINE_AA)

    def _draw(self, image: np.ndarray, pose: Pose, highlights: frozenset[LandmarkId]) -> None:
        height, width = image.shape[:2]

        def visible(landmark_id: int) -> bool:
            return (
                landmark_id < len(pose.landmarks)
                and pose.landmarks[landmark_id].visibility >= self._threshold
            )

        def pixel(landmark_id: int) -> tuple[int, int]:
            landmark = pose.landmarks[landmark_id]
            return int(landmark.x * width), int(landmark.y * height)

        for flagged in (False, True):  # red drawn last, so it is never covered
            color = _FLAGGED if flagged else _BONE
            for start, end in SKELETON:
                if ((start in highlights and end in highlights) == flagged
                        and visible(start) and visible(end)):
                    cv2.line(image, pixel(start), pixel(end), color, 5 if flagged else 2, cv2.LINE_AA)
            for landmark_id in LandmarkId:
                if (landmark_id in highlights) == flagged and visible(landmark_id):
                    cv2.circle(
                        image, pixel(landmark_id), 8 if flagged else 4,
                        _FLAGGED if flagged else _JOINT, -1, cv2.LINE_AA,
                    )