from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import TextIO

from pose_tracker.application.exercise_analyzer import RepResult
from pose_tracker.domain.exercise import Exercise
from pose_tracker.domain.rep_stats import feature_ranges

logger = logging.getLogger(__name__)

_DIVIDER = "-" * 60


class TextFileRepRecorder:
    """Appends each completed rep to a per-session text file, created on the first rep."""

    def __init__(
        self, directory: Path, clock: Callable[[], datetime] = datetime.now
    ) -> None:
        self._directory = directory
        self._clock = clock
        self._started = clock()
        self._file: TextIO | None = None
        self._total = 0
        self._clean = 0
        self.path: Path | None = None

    def record(self, exercise: Exercise, result: RepResult) -> None:
        try:
            file = self._file if self._file is not None else self._open(exercise)
            file.write(self._format_rep(exercise, result, self._clock()))
            file.flush()
        except OSError:
            logger.exception("Could not write rep to the session log")
            return
        self._total += 1
        if result.is_clean:
            self._clean += 1

    def close(self) -> None:
        if self._file is None:
            return
        try:
            self._file.write(self._format_footer())
        except OSError:
            logger.exception("Could not finalize the session log")
        finally:
            self._file.close()
            self._file = None

    def _open(self, exercise: Exercise) -> TextIO:
        self._directory.mkdir(parents=True, exist_ok=True)
        path = self._directory / f"{self._started:%Y-%m-%d_%H%M%S}_{exercise.key}.txt"
        file = path.open("w", encoding="utf-8")
        try:
            file.write(
                f"Exercise: {exercise.name}\n"
                f"Session started: {self._started:%Y-%m-%d %H:%M:%S}\n"
                f"{_DIVIDER}\n"
            )
            file.flush()
        except OSError:
            file.close()
            raise
        self._file, self.path = file, path
        return file

    @staticmethod
    def _format_rep(exercise: Exercise, result: RepResult, now: datetime) -> str:
        status = "clean" if result.is_clean else f"{len(result.violations)} issue(s)"
        lines = [
            f"Rep {result.rep_number} | {now:%H:%M:%S} | "
            f"{result.rep.duration_ms / 1000:.1f}s | {status}"
        ]
        lines.extend(
            f"  {name}: min {_fmt(low)}, max {_fmt(high)}"
            for name, (low, high) in feature_ranges(result.rep, exercise.logged_features).items()
        )
        lines.extend(
            f"  ! {v.rule_id}: {v.message} (measured {_fmt(v.measured)}, "
            f"limit {_fmt(v.limit)}, at {v.timestamp_ms / 1000:.1f}s into session)"
            for v in result.violations
        )
        return "\n".join(lines) + "\n"

    def _format_footer(self) -> str:
        return (
            f"{_DIVIDER}\n"
            f"Ended: {self._clock():%H:%M:%S}\n"
            f"Total reps: {self._total} | clean: {self._clean} | "
            f"with issues: {self._total - self._clean}\n"
        )

def _fmt(value: float) -> str:
    """One decimal for angles, three for small values (ratios, torso lengths)."""
    return f"{value:.1f}" if abs(value) >= 10 else f"{value:.3f}"

def _feature_ranges(
    rep: Rep, names: tuple[str, ...] | None
) -> Iterator[tuple[str, float, float]]:
    selected = names or tuple(f.name for f in dataclasses.fields(BodyFeatures))
    for name in selected:
        values = [
            value
            for sample in rep.samples
            if (value := getattr(sample.features, name)) is not None
        ]
        if values:
            yield name, min(values), max(values)