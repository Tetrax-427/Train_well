from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Any

from pose_tracker.errors import CalibrationError


def read_calibration_file(path: Path) -> dict[str, Any]:
    """The parsed file, or an empty dict if it does not exist (the defaults are then used)."""
    try:
        with path.open("rb") as handle:
            return tomllib.load(handle)
    except FileNotFoundError:
        return {}
    except tomllib.TOMLDecodeError as exc:
        raise CalibrationError(f"{path.name} is not valid TOML: {exc}") from exc
    except OSError as exc:
        raise CalibrationError(f"Cannot read {path}: {exc}") from exc