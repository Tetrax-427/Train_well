from __future__ import annotations

import math
from dataclasses import dataclass

from pose_tracker.domain.pose import Landmark


@dataclass(frozen=True, slots=True)
class Point2D:
    x: float
    y: float


def to_point(landmark: Landmark, aspect_ratio: float = 1.0) -> Point2D:
    """Project a landmark into the image plane.

    Normalized x/y are fractions of width/height, so x is scaled by
    ``width / height`` to make distances and angles isotropic.
    """
    return Point2D(landmark.x * aspect_ratio, landmark.y)


def angle_at(first: Point2D, vertex: Point2D, second: Point2D) -> float:
    """Interior angle in degrees (0-180) at ``vertex`` between the two rays.

    Raises:
        ValueError: if either ray has zero length.
    """
    ax, ay = first.x - vertex.x, first.y - vertex.y
    bx, by = second.x - vertex.x, second.y - vertex.y
    if (ax == 0.0 and ay == 0.0) or (bx == 0.0 and by == 0.0):
        raise ValueError("Cannot compute an angle with a zero-length segment")
    cross = ax * by - ay * bx
    dot = ax * bx + ay * by
    return math.degrees(abs(math.atan2(cross, dot)))

def distance(a: Point2D, b: Point2D) -> float:
    return math.hypot(a.x - b.x, a.y - b.y)


def midpoint(a: Point2D, b: Point2D) -> Point2D:
    return Point2D((a.x + b.x) / 2, (a.y + b.y) / 2)