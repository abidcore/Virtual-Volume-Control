"""
src/fps.py
==========
Lightweight, dependency-free FPS (frames-per-second) counter.

Uses an exponential moving average so the reported value is stable and
readable instead of jumping wildly between individual frames.
"""

import time


class FPSCounter:
    """Tracks and smooths the application's real-time frame rate."""

    def __init__(self, smoothing: float = 0.9) -> None:
        """
        Args:
            smoothing: Weight given to the previous FPS estimate (0-1).
                       Higher values produce a steadier on-screen reading.
        """
        self._smoothing = smoothing
        self._previous_time = time.time()
        self._fps = 0.0

    def update(self) -> float:
        """
        Call once per processed frame. Returns the current smoothed FPS.
        """
        current_time = time.time()
        elapsed = current_time - self._previous_time
        self._previous_time = current_time

        if elapsed <= 0:
            return self._fps

        instantaneous_fps = 1.0 / elapsed

        # Exponential moving average keeps the readout from flickering.
        self._fps = (self._smoothing * self._fps) + \
            ((1.0 - self._smoothing) * instantaneous_fps)

        return self._fps

    @property
    def fps(self) -> float:
        """Last computed smoothed FPS value."""
        return self._fps
