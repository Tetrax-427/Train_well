from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np

from pose_tracker.domain.pose import Landmark, LandmarkId, Pose
from pose_tracker.infrastructure.opencv_snapshot_painter import OpenCvSnapshotPainter

RED = [0, 0, 255]
WHITE = [255, 255, 255]


def black_png(directory: Path) -> Path:
    path = directory / "snapshot.png"  # PNG is lossless, so pixel values are exact
    cv2.imwrite(str(path), np.zeros((100, 100, 3), dtype=np.uint8))
    return path


def make_pose(points: dict[LandmarkId, tuple[float, float, float]]) -> Pose:
    landmarks = [Landmark(0.5, 0.5, 0.0, 0.0)] * 35  # invisible unless given
    for landmark_id, (x, y, visibility) in points.items():
        landmarks[landmark_id] = Landmark(x, y, 0.0, visibility)
    return Pose(tuple(landmarks))


POSE = make_pose({
    LandmarkId.LEFT_KNEE: (0.5, 0.5, 1.0),
    LandmarkId.LEFT_ANKLE: (0.2, 0.2, 1.0),
    LandmarkId.LEFT_HIP: (0.8, 0.8, 0.0),
})
PAINTER = OpenCvSnapshotPainter(visibility_threshold=0.5)


def test_flagged_joint_is_red_and_others_are_white(tmp_path: Path) -> None:
    image = PAINTER.paint(black_png(tmp_path), POSE, (LandmarkId.LEFT_KNEE,), overlay=True)
    assert image is not None
    assert image[50, 50].tolist() == RED
    assert image[20, 20].tolist() == WHITE


def test_invisible_landmarks_are_not_drawn(tmp_path: Path) -> None:
    image = PAINTER.paint(black_png(tmp_path), POSE, (), overlay=True)
    assert image is not None
    assert image[80, 80].tolist() == [0, 0, 0]


def test_overlay_off_leaves_the_image_untouched(tmp_path: Path) -> None:
    image = PAINTER.paint(black_png(tmp_path), POSE, (LandmarkId.LEFT_KNEE,), overlay=False)
    assert image is not None
    assert not image.any()


def test_unreadable_file_gives_none(tmp_path: Path) -> None:
    assert PAINTER.paint(tmp_path / "missing.jpg", POSE, (), overlay=True) is None

GHOST = [255, 229, 0]  # BGR cyan


def test_ghost_draws_only_what_moved_and_is_given_the_image_aspect_ratio(tmp_path: Path) -> None:
    original = make_pose({
        LandmarkId.LEFT_HIP: (0.8, 0.8, 1.0),
        LandmarkId.LEFT_KNEE: (0.5, 0.5, 1.0),
        LandmarkId.LEFT_ANKLE: (0.2, 0.2, 1.0),
    })
    corrected = make_pose({
        LandmarkId.LEFT_HIP: (0.8, 0.8, 1.0),
        LandmarkId.LEFT_KNEE: (0.5, 0.5, 1.0),
        LandmarkId.LEFT_ANKLE: (0.2, 0.8, 1.0),  # only the ankle moved
    })
    aspects: list[float] = []

    def ghost(aspect_ratio: float) -> Pose:
        aspects.append(aspect_ratio)
        return corrected

    image = PAINTER.paint(black_png(tmp_path), original, (), overlay=False, ghost=ghost)

    assert image is not None
    assert aspects == [1.0]  # the test image is square
    assert image[80, 20].tolist() == GHOST      # the corrected ankle (row = y, column = x)
    assert image[80, 80].tolist() == [0, 0, 0]  # the hip did not move, so it is not drawn


def test_ghost_that_cannot_be_computed_leaves_the_image_untouched(tmp_path: Path) -> None:
    image = PAINTER.paint(
        black_png(tmp_path), POSE, (), overlay=False, ghost=lambda _aspect: None
    )
    assert image is not None
    assert not image.any()