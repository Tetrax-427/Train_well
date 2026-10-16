from __future__ import annotations

import cv2
import numpy as np


class OpenCvDisplay:
    def __init__(self, window_name: str, quit_key: str = "q") -> None:
        self._window_name = window_name
        self._quit_code = ord(quit_key)

    def show(self, image: np.ndarray) -> bool:
        cv2.imshow(self._window_name, image)
        return (cv2.waitKey(1) & 0xFF) != self._quit_code

    def close(self) -> None:
        cv2.destroyAllWindows()