from __future__ import annotations

from dataclasses import dataclass
from operator import attrgetter

from pose_tracker.domain.exercise import Exercise
from pose_tracker.domain.features import BodyFeatures
from pose_tracker.domain.form import BandAtPeakRule, ReachAboveRule, StayAboveRule, TempoRule
from pose_tracker.domain.rep import RepThresholds
from pose_tracker.domain.view import CameraView


@dataclass(frozen=True, slots=True)
class HipThrustSettings:
    """Side view, upper back on a bench. Starting-point thresholds; tune against real footage."""

    lockout_hip_angle: float = 170.0     # shoulder-hip-knee at the top
    max_shin_angle_deg: float = 20.0     # shin vs vertical at the top
    min_neck_angle: float = 145.0        # ear-shoulder-hip
    min_rep_seconds: float = 1.0         # faster reps count as bouncing
    max_gate_tilt_deg: float = 50.0      # back must be within this of horizontal for reps to count
    rest_hip_angle: float = 135.0        # at/below this the hips are down
    leave_hip_angle: float = 150.0       # above this a thrust has started
    lead_in_ms: int = 1000


def build_hip_thrust(settings: HipThrustSettings = HipThrustSettings()) -> Exercise:
    s = settings

    def thrusting_hip_angle(features: BodyFeatures) -> float | None:
        """Drives rep counting, but only while you are lying back on the bench."""
        tilt = features.back_tilt_deg
        if tilt is None or abs(tilt) > s.max_gate_tilt_deg:
            return None
        return features.hip_angle

    return Exercise(
        key="hip_thrust",
        name="Hip Thrust",
        required_view=CameraView.SIDE,
        driver=thrusting_hip_angle,
        thresholds=RepThresholds(rest_angle=s.rest_hip_angle, leave_angle=s.leave_hip_angle),
        rules=(
            ReachAboveRule(
                "thrust_lockout", "Drive your hips all the way up until your body is one line",
                attrgetter("hip_angle"), s.lockout_hip_angle,
            ),
            BandAtPeakRule(
                "foot_placement", "Move your feet so your shins are vertical at the top",
                attrgetter("shin_angle_deg"), attrgetter("hip_angle"),
                0.0, s.max_shin_angle_deg,
            ),
            StayAboveRule(
                "head_position", "Keep your chin tucked and your neck in line",
                attrgetter("neck_angle"), s.min_neck_angle,
            ),
            TempoRule(
                "thrust_tempo", "Too fast: squeeze at the top and lower with control",
                s.min_rep_seconds,
            ),
        ),
        lead_in_ms=s.lead_in_ms,
        logged_features=("hip_angle", "shin_angle_deg", "knee_angle", "neck_angle", "back_tilt_deg"),
        position_hint="Lie with your upper back on the bench, side-on to the camera, whole body in frame",
        explanations={
            "thrust_lockout": (
                "If your hips don't reach full extension, your glutes never finish the "
                "contraction. Drive up until your shoulders, hips and knees form a straight line."
            ),
            "foot_placement": (
                "With your feet too close or too far, your shins aren't vertical at the top, "
                "so your quads or hamstrings take over from your glutes. Adjust your feet "
                "until your shins are upright when your hips are up."
            ),
            "head_position": (
                "Letting your head fall back or your chin lift pulls your neck out of line. "
                "Keep your chin tucked and your gaze forward."
            ),
            "thrust_tempo": (
                "A very fast rep means momentum is lifting the weight. Pause and squeeze "
                "your glutes at the top, and lower under control."
            ),
        },
    )