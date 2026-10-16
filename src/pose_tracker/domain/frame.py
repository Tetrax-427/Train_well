from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True, slots=True)
class Frame:
    """A BGR image with a monotonically increasing timestamp in milliseconds."""

    image: np.ndarray
    timestamp_ms: int