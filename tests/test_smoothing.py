from __future__ import annotations

import pytest

from pose_tracker.domain.filters import OneEuroConfig, OneEuroFilter
from pose_tracker.domain.pose import Landmark, Pose
from pose_tracker.domain.pose_smoother import PoseSmoother

DT = 1 / 30


def test_first_sample_passes_through() -> None:
    assert OneEuroFilter(OneEuroConfig()).filter(0.7, 0.0) == 0.7


def test_constant_signal_is_unchanged() -> None:
    f = OneEuroFilter(OneEuroConfig())
    outputs = [f.filter(0.5, i * DT) for i in range(30)]
    assert all(o == pytest.approx(0.5) for o in outputs)


def test_jitter_is_reduced() -> None:
    f = OneEuroFilter(OneEuroConfig())
    noisy = [0.5 + (0.005 if i % 2 else -0.005) for i in range(60)]
    outputs = [f.filter(v, i * DT) for i, v in enumerate(noisy)]
    tail = outputs[-20:]
    assert max(tail) - min(tail) < 0.005  # input swing is 0.01


def test_fast_motion_is_tracked() -> None:
    f = OneEuroFilter(OneEuroConfig())
    outputs = [f.filter(i * DT, i * DT) for i in range(31)]  # ramp 0 -> 1 in 1s
    assert outputs[-1] > 0.9


def test_non_increasing_timestamp_returns_last_value() -> None:
    f = OneEuroFilter(OneEuroConfig())
    f.filter(0.2, 1.0)
    assert f.filter(0.9, 1.0) == 0.2


def test_invalid_config_rejected() -> None:
    with pytest.raises(ValueError):
        OneEuroConfig(min_cutoff=0)


def test_pose_smoother_preserves_visibility_and_resets() -> None:
    smoother = PoseSmoother(OneEuroConfig())
    pose = Pose((Landmark(0.1, 0.2, 0.3, 0.8),))
    first = smoother.smooth(pose, 0)
    assert first.landmarks[0] == pose.landmarks[0]

    smoother.reset()
    moved = Pose((Landmark(0.9, 0.9, 0.9, 0.8),))
    assert smoother.smooth(moved, 33).landmarks[0] == moved.landmarks[0]