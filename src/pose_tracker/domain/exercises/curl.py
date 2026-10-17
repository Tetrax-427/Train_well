from __future__ import annotations

from dataclasses import dataclass
from operator import attrgetter

from pose_tracker.domain.exercise import Exercise
from pose_tracker.domain.form import ReachAboveRule, ReachBelowRule, StayBelowRule, StayStillRule
from pose_tracker.domain.motion_rules import SteadinessRule
from pose_tracker.domain.rep import RepThresholds
from pose_tracker.domain.view import CameraView


@dataclass(frozen=True, slots=True)
class CurlSettings:
    """Starting-point thresholds. Tune against real footage."""

    top_elbow_angle: float = 55.0        # at the top the elbow should bend to <= this
    bottom_elbow_angle: float = 160.0    # at the bottom the arm should extend to >= this
    max_upper_arm_angle: float = 30.0    # upper arm vs torso line (elbow drift)
    max_torso_swing_deg: float = 10.0    # lean may change by at most this during a rep
    max_unsteadiness: float = 0.025
    rest_elbow_angle: float = 150.0      # at/above this you are at the bottom
    leave_elbow_angle: float = 140.0     # below this a curl has started
    lead_in_ms: int = 1500               # bottom-position history kept with each rep


def build_curl(settings: CurlSettings = CurlSettings()) -> Exercise:
    s = settings
    elbow = attrgetter("elbow_angle")
    return Exercise(
        key="bicep_curl",
        name="Bicep Curl",
        required_view=CameraView.SIDE,
        driver=elbow,
        thresholds=RepThresholds(rest_angle=s.rest_elbow_angle, leave_angle=s.leave_elbow_angle),
        rules=(
            ReachBelowRule(
                "curl_top", "Curl all the way up and squeeze at the top",
                elbow, s.top_elbow_angle,
            ),
            ReachAboveRule(
                "curl_bottom", "Lower all the way down: fully straighten your arm",
                elbow, s.bottom_elbow_angle,
            ),
            StayBelowRule(
                "elbow_drift", "Keep your elbow pinned to your side",
                attrgetter("upper_arm_angle"), s.max_upper_arm_angle,
            ),
            StayStillRule(
                "torso_swing", "Don't swing your body: keep your torso still",
                attrgetter("torso_layback_deg"), s.max_torso_swing_deg,
            ),
            SteadinessRule(
                "control", "Jerky: slow down and control the weight", s.max_unsteadiness
            ),
        ),
        lead_in_ms=s.lead_in_ms,
        logged_features=("elbow_angle", "upper_arm_angle", "torso_layback_deg"),
        position_hint="Stand side-on with your arm and full body in frame",
        explanations={
            "curl_top": (
                "Stopping the curl short of the top leaves the most shortened position "
                "of the biceps untrained, so each rep does less work than it could."
            ),
            "curl_bottom": (
                "Not straightening your arm at the bottom shortens the range of motion, "
                "so the biceps work through less of the movement."
            ),
            "elbow_drift": (
                "When your elbow swings forward or back, your shoulders help lift the "
                "weight and the biceps get less of the work."
            ),
            "torso_swing": (
                "Swinging your torso builds momentum that lifts the weight for you and "
                "loads your lower back. If you need to swing, the weight is probably "
                "too heavy."
            ),
            "control": (
                "A shaky or jerky path means momentum is moving the weight instead of "
                "the muscle. Slow down and control both the lift and the lowering."
            ),
        },
    )