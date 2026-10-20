from __future__ import annotations

from pathlib import Path

import pytest

from pose_tracker.errors import CalibrationError
from pose_tracker.infrastructure.calibration_file import read_calibration_file


def test_a_missing_file_means_defaults(tmp_path: Path) -> None:
    assert read_calibration_file(tmp_path / "calibration.toml") == {}


def test_a_valid_file_is_parsed(tmp_path: Path) -> None:
    path = tmp_path / "calibration.toml"
    path.write_text('[squat]\ntarget_knee_angle = 110.0\ndisabled_rules = ["torso_lean"]\n')
    assert read_calibration_file(path) == {
        "squat": {"target_knee_angle": 110.0, "disabled_rules": ["torso_lean"]}
    }


def test_invalid_toml_is_a_calibration_error(tmp_path: Path) -> None:
    path = tmp_path / "calibration.toml"
    path.write_text("[squat\ntarget = ")
    with pytest.raises(CalibrationError, match="not valid TOML"):
        read_calibration_file(path)


def test_an_unreadable_path_is_a_calibration_error(tmp_path: Path) -> None:
    with pytest.raises(CalibrationError, match="Cannot read"):
        read_calibration_file(tmp_path)  # a directory