from __future__ import annotations

from dataclasses import dataclass
from operator import attrgetter

from pose_tracker.domain.exercise import Exercise
from pose_tracker.domain.form import MedianBandRule, ReachAboveRule, ReachBelowRule, StayBelowRule
from pose_tracker.domain.motion_rules import SteadinessRule
from pose_tracker.domain.rep import RepThresholds
from pose_tracker.domain.view import CameraView


@dataclass(frozen=True, slots=True)
class LatPulldownSettings:
    """Front view, both arms. Starting-point thresholds; tune against real footage.

    Grip is the horizontal distance between your wrists in shoulder widths.
    """

    min_grip_ratio: float
    max_grip_ratio: float
    max_depth_elevation_deg: float        # upper arms must come down to within this of vertical
    min_stretch_deg: float = 155.0        # at the top both elbows should extend to >= this
    max_bar_tilt: float = 0.30            # left/right wrist height gap, in shoulder widths
    max_unsteadiness: float = 0.03
    rest_elevation_deg: float = 120.0     # at/above this the arms are up (top position)
    leave_elevation_deg: float = 100.0    # below this a pull has started
    lead_in_ms: int = 1000                # top-position history kept with each rep


WIDE_GRIP = LatPulldownSettings(
    min_grip_ratio=1.5, max_grip_ratio=3.0, max_depth_elevation_deg=65.0
)
CLOSE_GRIP = LatPulldownSettings(
    min_grip_ratio=0.0, max_grip_ratio=1.1, max_depth_elevation_deg=55.0
)


def _build(key: str, name: str, s: LatPulldownSettings, grip_message: str, grip_why: str) -> Exercise:
    elevation = attrgetter("arm_elevation_deg")
    return Exercise(
        key=key,
        name=name,
        required_view=CameraView.FRONT,
        driver=elevation,
        thresholds=RepThresholds(
            rest_angle=s.rest_elevation_deg, leave_angle=s.leave_elevation_deg
        ),
        rules=(
            ReachBelowRule(
                "pulldown_depth", "Pull the bar down to your upper chest, elbows down",
                elevation, s.max_depth_elevation_deg,
            ),
            ReachAboveRule(
                "pulldown_stretch", "Let the bar all the way up: fully straighten your arms",
                attrgetter("arm_bend_deg"), s.min_stretch_deg,
            ),
            MedianBandRule(
                "grip_width", grip_message,
                attrgetter("grip_ratio"), s.min_grip_ratio, s.max_grip_ratio,
            ),
            StayBelowRule(
                "bar_level", "Keep the bar level: pull both sides evenly",
                attrgetter("wrist_gap"), s.max_bar_tilt,
            ),
            SteadinessRule("control", "Jerky: pull smoothly, don't yank", s.max_unsteadiness),
        ),
        lead_in_ms=s.lead_in_ms,
        logged_features=("arm_elevation_deg", "arm_bend_deg", "grip_ratio", "wrist_gap"),
        position_hint="Sit facing the camera with both arms and your upper body in frame",
        explanations={
            "pulldown_depth": (
                "Stopping short means your lats work through less of the movement. Pull your "
                "elbows down toward your sides until the bar reaches your upper chest."
            ),
            "pulldown_stretch": (
                "Not letting your arms fully straighten at the top skips the stretch at the "
                "start of each rep, so the lats train through a shorter range."
            ),
            "grip_width": grip_why,
            "bar_level": (
                "A tilted bar means one side is pulling harder than the other, so the "
                "stronger side does more of the work and the weaker one falls behind."
            ),
            "control": (
                "A jerky pull means momentum is moving the bar instead of your back. Slow "
                "down and control both the pull and the return."
            ),
        },
    )


def build_wide_pulldown(settings: LatPulldownSettings = WIDE_GRIP) -> Exercise:
    return _build(
        "lat_pulldown_wide", "Lat Pulldown (Wide Grip)", settings,
        grip_message="Adjust your grip: wide grip, hands well outside your shoulders",
        grip_why=(
            "A wide grip shifts the work to the outer lats. If your hands are too close, it "
            "becomes a regular pulldown, and if they are far too wide the shoulders are "
            "stressed and the range of motion shrinks."
        ),
    )


def build_close_pulldown(settings: LatPulldownSettings = CLOSE_GRIP) -> Exercise:
    return _build(
        "lat_pulldown_close", "Lat Pulldown (Close Grip)", settings,
        grip_message="Adjust your grip: close grip, hands about shoulder width or closer",
        grip_why=(
            "A close grip lets your elbows travel closer to your body for a longer pull. If "
            "your hands drift wider than your shoulders you lose that, and it turns into a "
            "wide-grip pulldown."
        ),
    )