from __future__ import annotations

from dataclasses import dataclass
from operator import attrgetter

from pose_tracker.domain.exercise import Exercise
from pose_tracker.domain.features import BodyFeatures
from pose_tracker.domain.form import (
    MedianBandRule,
    Selector,
    StayAboveRule,
    StayBelowRule,
    StayStillRule,
)
from pose_tracker.domain.rep import RepThresholds
from pose_tracker.domain.view import CameraView


@dataclass(frozen=True, slots=True)
class PlankSettings:
    """Side view. A hold counts as one 'rep'. Starting-point thresholds; tune against real footage."""

    max_hip_sag_deg: float = 10.0
    max_hip_pike_deg: float = 10.0
    min_knee_angle: float = 160.0
    min_neck_angle: float = 145.0         # ear-shoulder-hip
    max_elbow_offset: float = 0.3         # elbow vs shoulder along the body, torso lengths
    max_hip_wobble_deg: float = 8.0       # spread of the hip angle during the hold
    rest_incline_deg: float = 45.0        # at/above this you are not in a plank
    leave_incline_deg: float = 30.0       # below this the hold has started
    min_hold_ms: int = 5000               # shorter holds are not counted
    pose_grace_ms: int = 1500             # tracking may drop out this long without ending the hold


def build_plank(settings: PlankSettings = PlankSettings()) -> Exercise:
    s = settings

    def held(name: str) -> Selector:
        """The feature, but only while the body is actually in the plank position, so getting
        down into and up out of the plank never counts against you."""

        def select(features: BodyFeatures) -> float | None:
            incline = features.body_incline_deg
            if incline is None or incline >= s.leave_incline_deg:
                return None
            return getattr(features, name)

        return select

    return Exercise(
        key="plank",
        name="Plank",
        required_view=CameraView.SIDE,
        driver=attrgetter("body_incline_deg"),
        thresholds=RepThresholds(rest_angle=s.rest_incline_deg, leave_angle=s.leave_incline_deg),
        rules=(
            StayBelowRule(
                "hip_sag", "Hips sagging, squeeze your core and glutes",
                held("hip_sag_deg"), s.max_hip_sag_deg,
            ),
            StayAboveRule(
                "hip_pike", "Hips too high, keep your body in one line",
                held("hip_sag_deg"), -s.max_hip_pike_deg,
            ),
            StayAboveRule(
                "knee_bend", "Keep your legs straight",
                held("knee_angle"), s.min_knee_angle,
            ),
            StayAboveRule(
                "head_position", "Keep your head in line with your spine",
                held("neck_angle"), s.min_neck_angle,
            ),
            MedianBandRule(
                "support_position", "Place your elbows (or hands) directly under your shoulders",
                held("elbow_offset"), -s.max_elbow_offset, s.max_elbow_offset,
            ),
            StayStillRule(
                "hold_steady", "Hold still: your hips are bobbing",
                held("hip_sag_deg"), s.max_hip_wobble_deg,
            ),
        ),
        logged_features=("body_incline_deg", "hip_sag_deg", "knee_angle", "neck_angle", "elbow_offset"),
        position_hint="Get into a plank, side-on to the camera, whole body in frame",
        timed=True,
        min_rep_ms=s.min_hold_ms,
        pose_grace_ms=s.pose_grace_ms,
        explanations={
            "hip_sag": (
                "Sagging hips mean your core and glutes aren't holding the plank, which puts "
                "extra load on your lower back."
            ),
            "hip_pike": (
                "Raised hips take the load off your core and make the hold easier than it "
                "should be."
            ),
            "knee_bend": (
                "Bent knees shorten the lever and make the hold easier. Your body should "
                "stay one straight line from shoulders to ankles."
            ),
            "head_position": (
                "A dropped or craned head pulls your neck out of line with your spine and "
                "can strain it. Look at the floor just ahead of your hands."
            ),
            "support_position": (
                "Elbows or hands far in front of or behind your shoulders overload your "
                "shoulders. Stack them directly under your shoulders."
            ),
            "hold_steady": (
                "Hips bobbing up and down means your core is tiring or not bracing. Squeeze "
                "your abs and glutes to hold a still, flat line. Settling in at the start of "
                "a hold can also show up here."
            ),
        },
    )