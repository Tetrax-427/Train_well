from __future__ import annotations

import pytest

from pose_tracker.domain.geometry import Point2D, angle_at, to_point
from pose_tracker.domain.pose import Landmark


def test_right_angle() -> None:
    assert angle_at(Point2D(1, 0), Point2D(0, 0), Point2D(0, 1)) == pytest.approx(90)


def test_straight_line_is_180() -> None:
    assert angle_at(Point2D(-1, 0), Point2D(0, 0), Point2D(1, 0)) == pytest.approx(180)


def test_overlapping_rays_is_zero() -> None:
    assert angle_at(Point2D(1, 0), Point2D(0, 0), Point2D(2, 0)) == pytest.approx(0)


def test_angle_is_symmetric() -> None:
    a, v, b = Point2D(1, 2), Point2D(0, 0), Point2D(3, -1)
    assert angle_at(a, v, b) == pytest.approx(angle_at(b, v, a))


def test_zero_length_segment_raises() -> None:
    with pytest.raises(ValueError):
        angle_at(Point2D(0, 0), Point2D(0, 0), Point2D(1, 1))


def test_to_point_applies_aspect_ratio() -> None:
    point = to_point(Landmark(0.5, 0.5, 0.0, 1.0), aspect_ratio=16 / 9)
    assert point.x == pytest.approx(0.5 * 16 / 9)
    assert point.y == 0.5