from __future__ import annotations

from dataclasses import dataclass
from operator import attrgetter

from pose_tracker.domain.exercise import Exercise
from pose_tracker.domain.form import (
    BandAtRestRule,
    DriftFromRestRule,
    ReachAboveRule,
    ReachBelowRule,
    StayAboveRule,
    StayStillRule,
)
from pose_tracker.domain.motion_rules import PathDeviationRule, SteadinessRule
from pose_tracker.domain.rep import RepThresholds
from pose_tracker.domain.view import CameraView


@dataclass(frozen=True, slots=True)
class BentOverRowSettings:
    """Side view. Starting-point thresholds; tune against real footage."""

    top_elbow_angle: float = 105.0        # at the top the elbow should bend to <= this
    bottom_elbow_angle: float = 160.0     # at the bottom the arm should extend to >= this
    min_hinge_deg: float = 30.0           # torso angle from vertical at setup
    max_hinge_deg: float = 75.0
    max_torso_change_deg: float = 15.0    # the torso may move by at most this during a rep
    max_chord_shrink: float = 0.08        # shoulder-hip chord ratio may drop by at most 8%
    min_neck_angle: float = 140.0
    max_path_deviation: float = 0.20      # hand vs straight line, in torso lengths
    max_unsteadiness: float = 0.03
    rest_elbow_angle: float = 150.0       # at/above this the arms hang
    leave_elbow_angle: float = 135.0      # below this a pull has started
    lead_in_ms: int = 1000


def build_bent_over_row(settings: BentOverRowSettings = BentOverRowSettings()) -> Exercise:
    s = settings
    elbow = attrgetter("elbow_angle")
    torso_lean = attrgetter("torso_lean_deg")
    return Exercise(
        key="bent_over_row",
        name="Bent-Over Row",
        required_view=CameraView.SIDE,
        driver=elbow,
        thresholds=RepThresholds(rest_angle=s.rest_elbow_angle, leave_angle=s.leave_elbow_angle),
        rules=(
            ReachBelowRule(
                "row_top", "Pull your elbows back until the weight reaches your lower ribs",
                elbow, s.top_elbow_angle,
            ),
            ReachAboveRule(
                "row_stretch", "Lower all the way down: fully straighten your arms",
                elbow, s.bottom_elbow_angle,
            ),
            BandAtRestRule(
                "row_hinge", "Hinge from your hips: lean forward but keep your back flat",
                torso_lean, s.min_hinge_deg, s.max_hinge_deg,
            ),
            StayStillRule(
                "torso_swing", "Don't heave your body: keep your torso still",
                torso_lean, s.max_torso_change_deg,
            ),
            DriftFromRestRule(
                "back_rounding", "Possible back rounding: chest up, keep your spine neutral",
                attrgetter("torso_thigh_ratio"), s.max_chord_shrink, direction=-1, relative=True,
            ),
            PathDeviationRule(
                "bar_path", "Pull in a smooth line: no jerking", s.max_path_deviation
            ),
            SteadinessRule("control", "Unsteady: slow down, control the weight", s.max_unsteadiness),
            StayAboveRule(
                "head_position", "Keep your neck in line with your spine",
                attrgetter("neck_angle"), s.min_neck_angle,
            ),
        ),
        lead_in_ms=s.lead_in_ms,
        logged_features=("elbow_angle", "torso_lean_deg", "torso_thigh_ratio", "neck_angle"),
        position_hint="Hinge forward side-on to the camera, whole body in frame",
        explanations={
            "row_top": (
                "Stopping the pull short leaves your mid-back working through less of its "
                "range. Drive your elbows back until the weight reaches your lower ribs."
            ),
            "row_stretch": (
                "Not straightening your arms at the bottom shortens the range of motion "
                "and skips the stretch at the start of each rep."
            ),
            "row_hinge": (
                "If your torso is too upright the exercise shifts to your upper traps, and "
                "if it is too flat your lower back takes the strain. Hinge from the hips "
                "to roughly 45 degrees with a flat back."
            ),
            "torso_swing": (
                "Heaving your body up to bring the weight with you uses momentum and loads "
                "your lower back. If you need to, the weight is probably too heavy."
            ),
            "back_rounding": (
                "Your shoulder-to-hip distance shrank during the pull, which suggests your "
                "spine curled forward. A rounded back under load stresses the spinal discs. "
                "This is an estimate from the camera, not a spine measurement."
            ),
            "bar_path": (
                "The weight should move in a smooth line toward your hips. A jerky or "
                "wandering path wastes energy and strains your shoulders."
            ),
            "control": (
                "A shaky path means momentum is moving the weight instead of your back. "
                "Slow down and control both the pull and the lowering."
            ),
            "head_position": (
                "Craning your head up or dropping it breaks the line of your spine. Look "
                "at the floor a few feet ahead to keep your neck neutral."
            ),
        },
    )