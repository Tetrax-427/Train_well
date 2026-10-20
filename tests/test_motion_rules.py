from __future__ import annotations

import math

import pytest

from pose_tracker.domain.features import BodyFeatures
from pose_tracker.domain.motion_rules import PathDeviationRule, SteadinessRule
from pose_tracker.domain.pose import Pose
from pose_tracker.domain.rep import Rep, Sample

PATH = PathDeviationRule("path", "straight", limit=0.15)
STEADY = SteadinessRule("steady", "control", limit=0.015)


def rep_from_track(track: list[tuple[float, float]], lead_in: int = 0) -> Rep:
    samples = tuple(
        Sample(i * 33, Pose(()), BodyFeatures(None, None, hand_x=x, hand_y=y))
        for i, (x, y) in enumerate(track)
    )
    return Rep(samples, lead_in_count=lead_in)


DOWN = [(0.0, 2.0 - (j + 1) / 9) for j in range(9)]  # straight descent, 1.89 -> 1.0


def test_straight_press_has_no_path_violation() -> None:
    up = [(0.0, 1.0 + i / 9) for i in range(10)]
    assert PATH.evaluate(rep_from_track(up + DOWN)) is None


def test_bowed_press_is_flagged() -> None:
    up = [(0.3 * math.sin(math.pi * i / 9), 1.0 + i / 9) for i in range(10)]
    violation = PATH.evaluate(rep_from_track(up + DOWN))
    assert violation is not None
    assert violation.measured == pytest.approx(0.3 * math.sin(4 * math.pi / 9))


def test_tiny_movements_are_not_judged() -> None:
    assert PATH.evaluate(rep_from_track([(0.0, 1.0), (0.3, 1.05), (0.0, 1.1)])) is None


def test_smooth_motion_is_steady() -> None:
    assert STEADY.evaluate(rep_from_track([(0.0, 1.0 + i * 0.02) for i in range(30)])) is None


def test_shaky_hand_is_flagged() -> None:
    shaky = [(0.05 if i % 2 else -0.05, 1.0 + i * 0.02) for i in range(30)]
    violation = STEADY.evaluate(rep_from_track(shaky))
    assert violation is not None
    assert violation.measured == pytest.approx(0.05 * 8 / 7, rel=1e-3)


def test_shake_in_the_lead_in_is_ignored() -> None:
    shaky = [(0.05 if i % 2 else -0.05, 1.0) for i in range(8)]
    smooth = [(0.0, 1.0 + i * 0.02) for i in range(20)]
    assert STEADY.evaluate(rep_from_track(shaky + smooth, lead_in=8)) is None


def test_too_few_samples_are_not_judged() -> None:
    assert STEADY.evaluate(rep_from_track([(0.0, 1.0), (0.1, 1.1)])) is None


def test_even_or_tiny_window_rejected() -> None:
    with pytest.raises(ValueError):
        SteadinessRule("s", "m", 0.01, window=4)

PATH_INVERTED = PathDeviationRule("path", "straight", limit=0.15, inverted=True)
UP = [(0.0, 1.0 + j / 9) for j in range(1, 10)]


def test_inverted_rule_accepts_a_straight_descent_and_ascent() -> None:
    down = [(0.0, 2.0 - i / 9) for i in range(10)]  # 2.0 -> 1.0
    assert PATH_INVERTED.evaluate(rep_from_track(down + UP)) is None


def test_inverted_rule_flags_a_bowed_descent() -> None:
    down = [(0.3 * math.sin(math.pi * i / 9), 2.0 - i / 9) for i in range(10)]
    violation = PATH_INVERTED.evaluate(rep_from_track(down + UP))
    assert violation is not None
    assert violation.measured == pytest.approx(0.3 * math.sin(4 * math.pi / 9))