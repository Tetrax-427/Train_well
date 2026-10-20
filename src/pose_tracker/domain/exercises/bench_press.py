from __future__ import annotations

from dataclasses import dataclass
from operator import attrgetter

from pose_tracker.domain.exercise import Exercise
from pose_tracker.domain.features import BodyFeatures
from pose_tracker.domain.form import (
    ReachAboveRule,
    ReachBelowRule,
    StayAboveRule,
    StayBelowRule,
    StayStillRule,
)
from pose_tracker.domain.motion_rules import PathDeviationRule, SteadinessRule
from pose_tracker.domain.rep import RepThresholds
from pose_tracker.domain.view import CameraView


@dataclass(frozen=True, slots=True)
class BenchPressSettings:
    """Bench or floor press, side view. Starting-point thresholds; tune against real footage."""

    bottom_elbow_angle: float = 95.0     # at the bottom the elbow should bend to <= this
    lockout_elbow_angle: float = 165.0   # at the top the elbow should extend to >= this
    max_hip_lift_deg: float = 12.0       # hips may sit at most this far above the shoulders
    max_arch_deg: float = 12.0           # shoulders may sit at most this far above the hips
    min_neck_angle: float = 145.0        # ear-shoulder-hip; lower = head lifted off the bench
    max_path_deviation: float = 0.15     # hand vs straight line, in torso lengths
    max_hand_drift: float = 0.30         # horizontal travel of the hand, in torso lengths
    max_unsteadiness: float = 0.03       # hand shake (RMS), in torso lengths
    max_lying_tilt_deg: float = 30.0     # shoulder-hip line must be flatter than this to count reps
    rest_elbow_angle: float = 155.0      # at/above this you are at the top
    leave_elbow_angle: float = 140.0     # below this the descent has started
    lead_in_ms: int = 1500               # top-position history kept with each rep


def build_bench_press(settings: BenchPressSettings = BenchPressSettings()) -> Exercise:
    s = settings
    elbow = attrgetter("elbow_angle")
    back_tilt = attrgetter("back_tilt_deg")

    def lying_elbow_angle(features: BodyFeatures) -> float | None:
        """Drives rep counting, but only while you are lying down."""
        tilt = features.back_tilt_deg
        if tilt is None or abs(tilt) > s.max_lying_tilt_deg:
            return None
        return features.elbow_angle

    return Exercise(
        key="bench_press",
        name="Bench Press",
        required_view=CameraView.SIDE,
        driver=lying_elbow_angle,
        thresholds=RepThresholds(rest_angle=s.rest_elbow_angle, leave_angle=s.leave_elbow_angle),
        rules=(
            ReachBelowRule(
                "bench_depth", "Lower the weight to your chest", elbow, s.bottom_elbow_angle
            ),
            ReachAboveRule(
                "bench_lockout", "Press all the way up, lock out your arms",
                elbow, s.lockout_elbow_angle,
            ),
            StayBelowRule(
                "hips_lifted", "Keep your hips down on the bench or floor",
                back_tilt, s.max_hip_lift_deg,
            ),
            StayAboveRule(
                "back_arch", "Don't over-arch: keep your back flat and your chest relaxed",
                back_tilt, -s.max_arch_deg,
            ),
            PathDeviationRule(
                "bar_path", "Keep the press path straight", s.max_path_deviation, inverted=True
            ),
            StayStillRule(
                "bar_drift", "Press straight up and down, not forward or back",
                attrgetter("hand_x"), s.max_hand_drift,
            ),
            SteadinessRule("control", "Unsteady: slow down, control the weight", s.max_unsteadiness),
            StayAboveRule(
                "head_position", "Keep your head resting back on the bench",
                attrgetter("neck_angle"), s.min_neck_angle,
            ),
        ),
        lead_in_ms=s.lead_in_ms,
        logged_features=("elbow_angle", "back_tilt_deg", "neck_angle", "hand_x"),
        position_hint="Lie on the bench or floor, side-on to the camera, whole body in frame",
        explanations={
            "bench_depth": (
                "Stopping above chest level shortens the range of motion, so your chest and "
                "triceps get less work. Lower until the weight reaches your chest (or your "
                "upper arms touch the floor in a floor press)."
            ),
            "bench_lockout": (
                "Pressing short of full extension leaves the finish of the movement untrained "
                "and never stacks the weight over your shoulders."
            ),
            "hips_lifted": (
                "Lifting your hips turns the press into a bridge: your legs and lower back "
                "take over some of the work and your lower back is loaded unevenly."
            ),
            "back_arch": (
                "Your shoulders sit well above your hips, which suggests a big arch in your "
                "lower back. A small natural arch is fine, but an exaggerated one compresses "
                "the lower spine. This is an estimate from the camera, not a spine measurement."
            ),
            "bar_path": (
                "The weight should travel in a smooth, straight line. A wavering path wastes "
                "energy and puts uneven stress on your shoulders."
            ),
            "bar_drift": (
                "Pressing forward or back instead of straight up and down means the weight "
                "isn't stacked over your shoulders, so it is harder to control and strains "
                "the shoulder joint."
            ),
            "control": (
                "A shaky path means the weight is moving you rather than you moving it, which "
                "often signals the load is too heavy or the tempo too fast."
            ),
            "head_position": (
                "Lifting your head off the bench pulls your neck out of line with your spine "
                "and strains it. Keep the back of your head resting on the bench or floor."
            ),
        },
    )