from __future__ import annotations

from dataclasses import dataclass
from operator import attrgetter

from pose_tracker.domain.exercise import Exercise
from pose_tracker.domain.features import BodyFeatures
from pose_tracker.domain.form import (
    BandAtRestRule,
    ReachAboveRule,
    ReachBelowRule,
    StayAboveRule,
    StayBelowRule,
)
from pose_tracker.domain.rep import RepThresholds
from pose_tracker.domain.view import CameraView


@dataclass(frozen=True, slots=True)
class PushUpSettings:
    """Starting-point thresholds. Tune against real footage."""

    bottom_elbow_angle: float = 95.0     # elbow should bend to <= this at the bottom
    lockout_elbow_angle: float = 165.0   # elbow should extend to >= this at the top
    max_hip_sag_deg: float = 12.0        # hips below the shoulder-ankle line
    max_hip_pike_deg: float = 12.0       # hips above the shoulder-ankle line
    min_knee_angle: float = 160.0        # legs must stay at least this straight
    max_hand_offset: float = 0.3         # hand vs shoulder at the top, torso lengths, either way
    min_neck_angle: float = 145.0        # ear-shoulder-hip; lower = head dropped or craned
    max_plank_incline_deg: float = 35.0  # body must be flatter than this for reps to count
    rest_elbow_angle: float = 150.0      # at/above this you are at the top
    leave_elbow_angle: float = 135.0     # below this a rep has started
    lead_in_ms: int = 1000               # top-position history kept with each rep


def build_push_up(settings: PushUpSettings = PushUpSettings()) -> Exercise:
    def plank_elbow_angle(features: BodyFeatures) -> float | None:
        """Drives rep counting, but only while the body is roughly horizontal."""
        incline = features.body_incline_deg
        if incline is None or incline > settings.max_plank_incline_deg:
            return None
        return features.elbow_angle

    elbow = attrgetter("elbow_angle")
    hip_sag = attrgetter("hip_sag_deg")
    return Exercise(
        key="push_up",
        name="Push-up",
        required_view=CameraView.SIDE,
        driver=plank_elbow_angle,
        thresholds=RepThresholds(
            rest_angle=settings.rest_elbow_angle, leave_angle=settings.leave_elbow_angle
        ),
        rules=(
            ReachBelowRule(
                "pushup_depth", "Lower your chest more, bend your elbows to about 90 degrees",
                elbow, settings.bottom_elbow_angle,
            ),
            ReachAboveRule(
                "pushup_lockout", "Push all the way up, straighten your arms",
                elbow, settings.lockout_elbow_angle,
            ),
            StayBelowRule(
                "hip_sag", "Hips sagging, squeeze your core and glutes",
                hip_sag, settings.max_hip_sag_deg,
            ),
            StayAboveRule(
                "hip_pike", "Hips too high, keep your body in one line",
                hip_sag, -settings.max_hip_pike_deg,
            ),
            StayAboveRule(
                "knee_bend", "Keep your legs straight",
                attrgetter("knee_angle"), settings.min_knee_angle,
            ),
            StayAboveRule(
                "head_position", "Keep your head in line with your spine",
                attrgetter("neck_angle"), settings.min_neck_angle,
            ),
            BandAtRestRule(
                "hand_placement", "Place your hands directly under your shoulders",
                attrgetter("hand_offset"),
                -settings.max_hand_offset, settings.max_hand_offset,
            ),
        ),
        explanations={
            "pushup_depth": (
                "Stopping short of about 90 degrees at the elbow trains less range of "
                "motion, so your chest and triceps do less of the work."
            ),
            "pushup_lockout": (
                "Not fully straightening your arms at the top skips the finish of the push, "
                "so the rep isn't a full range of motion."
            ),
            "hip_sag": (
                "Sagging hips mean your core and glutes aren't holding the plank, which puts "
                "extra load on your lower back."
            ),
            "hip_pike": (
                "Raised hips take load off your chest and core and make the push-up easier "
                "than it should be."
            ),
            "knee_bend": (
                "Bent knees shorten the lever and make the push-up easier. Your body should "
                "stay one straight line from shoulders to ankles."
            ),
            "head_position": (
                "A dropped or craned head pulls your neck out of line with your spine and "
                "can strain it. Look slightly ahead of your hands to keep it neutral."
            ),
            "hand_placement": (
                "Hands far in front of or behind your shoulders change the leverage on your "
                "shoulders and wrists. At the top they should sit roughly under your shoulders."
            ),
        },
        lead_in_ms=settings.lead_in_ms,
        logged_features=("elbow_angle", "hip_sag_deg", "knee_angle", "neck_angle", "hand_offset"),
        position_hint="Get into a straight plank, side-on to the camera",
    )