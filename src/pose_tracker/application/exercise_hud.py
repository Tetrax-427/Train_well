from __future__ import annotations

from collections.abc import Sequence

from pose_tracker.application.exercise_analyzer import AnalysisStatus, ExerciseAnalyzer
from pose_tracker.domain.pose import Pose
from pose_tracker.domain.view import CameraView
from pose_tracker.application.position_hint import position_hint



class ExerciseHudAnalyzer:
    """Adapts ExerciseAnalyzer to the PoseAnalyzer interface by producing overlay text."""

    def __init__(self, analyzer: ExerciseAnalyzer) -> None:
        self._analyzer = analyzer

    def analyze(
        self, pose: Pose | None, timestamp_ms: int, aspect_ratio: float
    ) -> Sequence[str]:
        status = self._analyzer.update(pose, timestamp_ms, aspect_ratio)
        return self._format(status)

    def _format(self, status: AnalysisStatus) -> list[str]:
        exercise = self._analyzer.exercise
        lines = [f"{exercise.name} | view: {status.view.name}", f"Reps: {status.rep_count}"]

        if not status.view_ok:
            if status.view is CameraView.UNKNOWN:
                lines.append("Step back so your full body is in frame")
            else:
                lines.append(_VIEW_HINTS.get(exercise.required_view, "Adjust your position"))
        elif status.driver_value is None:
            lines.append(exercise.position_hint)
        else:
            lines.append(f"Angle: {status.driver_value:.0f} deg")

        result = status.last_result
        if result is not None:
            if result.is_clean:
                lines.append(f"Rep {result.rep_number}: good form")
            else:
                lines.extend(f"Rep {result.rep_number}: {v.message}" for v in result.violations)
        return lines