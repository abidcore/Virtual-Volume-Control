"""
src/gesture_detector.py
========================
Translates raw hand-landmark data into discrete, high-level gestures
that the VolumeController can act on.

Recognized gestures
--------------------
- VOLUME_CONTROL : thumb + index finger extended, other three fingers
                    curled -> the thumb-index pixel distance drives the
                    system volume level
- MUTE_TOGGLE    : closed fist held for MUTE_HOLD_FRAMES consecutive
                    frames -> toggles mute/unmute
- IDLE           : no recognized control gesture

Design notes
------------
- The raw thumb-index distance is extremely sensitive to natural hand
  tremor and MediaPipe landmark jitter. A rolling-average "stabilization"
  window smooths the distance signal before it is converted into a
  volume percentage (see GESTURE STABILIZATION below).
- Mode transitions (e.g. entering volume-control mode) are debounced so
  a single stray frame doesn't cause the on-screen mode label to flicker.
- Mute toggling requires a sustained fist gesture plus a cooldown timer,
  preventing a single accidental fist frame from muting/unmuting
  repeatedly.
"""

import time
from collections import deque
from dataclasses import dataclass
from enum import Enum, auto
from typing import List, Optional, Tuple

from config import settings
from src.hand_tracker import HandTracker


class Gesture(Enum):
    """All gestures the system can recognize."""
    NONE = auto()
    VOLUME_CONTROL = auto()
    MUTE_TOGGLE = auto()


@dataclass
class GestureResult:
    """Container describing the gesture detected on the current frame."""
    gesture: Gesture
    distance: float = 0.0                       # stabilized thumb-index distance
    thumb_point: Tuple[int, int] = (0, 0)
    index_point: Tuple[int, int] = (0, 0)
    raw_label: str = "IDLE"                      # human-readable, shown on the HUD


class GestureDetector:
    """
    Stateful gesture recognizer for the volume-control pipeline. Holds a
    rolling distance buffer, a mode-transition debounce counter, and mute
    gesture/cooldown state between frames.
    """

    THUMB_TIP = 4
    INDEX_TIP = 8

    def __init__(self, tracker: HandTracker) -> None:
        self._tracker = tracker

        # Rolling window of recent raw distances, used to stabilize the
        # volume signal against frame-to-frame landmark jitter.
        self._distance_history: deque = deque(maxlen=settings.STABILIZATION_WINDOW)

        self._candidate_gesture = Gesture.NONE
        self._candidate_streak = 0

        self._fist_streak = 0
        self._last_mute_toggle_time = 0.0

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def detect(self, landmark_list: List[Tuple[int, int, int]]) -> GestureResult:
        """Main entry point: returns the gesture detected on this frame."""
        if not landmark_list:
            self._reset_streak()
            self._distance_history.clear()
            self._fist_streak = 0
            return GestureResult(Gesture.NONE, raw_label="NO HAND")

        fingers = self._tracker.fingers_up(landmark_list)
        thumb, index, middle, ring, pinky = fingers

        thumb_point = self._point_of(landmark_list, self.THUMB_TIP)
        index_point = self._point_of(landmark_list, self.INDEX_TIP)

        # --- 1) Closed fist -> Mute toggle candidate ---------------------
        if fingers == [0, 0, 0, 0, 0]:
            self._distance_history.clear()
            return self._handle_mute_gesture(thumb_point, index_point)

        self._fist_streak = 0

        # --- 2) Thumb + Index extended, others curled -> Volume control --
        if thumb and index and not middle and not ring and not pinky:
            raw_distance = self._tracker.find_distance(
                self.THUMB_TIP, self.INDEX_TIP, landmark_list
            )
            if raw_distance is None:
                self._distance_history.clear()
                self._reset_streak()
                return GestureResult(Gesture.NONE, thumb_point=thumb_point,
                                      index_point=index_point, raw_label="IDLE")

            stabilized_distance = self._stabilize(raw_distance)

            if not self._debounced(Gesture.VOLUME_CONTROL):
                return GestureResult(
                    Gesture.NONE, stabilized_distance, thumb_point, index_point,
                    "VOLUME_CONTROL (confirming)"
                )

            return GestureResult(
                Gesture.VOLUME_CONTROL, stabilized_distance, thumb_point,
                index_point, "VOLUME_CONTROL"
            )

        # --- 3) No recognized control gesture -----------------------------
        self._distance_history.clear()
        self._reset_streak()
        return GestureResult(Gesture.NONE, thumb_point=thumb_point,
                              index_point=index_point, raw_label="IDLE")

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _point_of(landmark_list: List[Tuple[int, int, int]],
                   landmark_id: int) -> Tuple[int, int]:
        for lm_id, x, y in landmark_list:
            if lm_id == landmark_id:
                return x, y
        return 0, 0

    def _stabilize(self, raw_distance: float) -> float:
        """
        Gesture stabilization: returns the rolling average of the last
        STABILIZATION_WINDOW raw distance readings instead of the noisy
        instantaneous value.
        """
        self._distance_history.append(raw_distance)
        return sum(self._distance_history) / len(self._distance_history)

    def _reset_streak(self) -> None:
        self._candidate_gesture = Gesture.NONE
        self._candidate_streak = 0

    def _debounced(self, gesture: Gesture) -> bool:
        """
        Requires a gesture to be seen for GESTURE_HOLD_FRAMES consecutive
        frames before it is considered "confirmed". This prevents a single
        noisy frame from flipping the mode label or the active control
        state unnecessarily.
        """
        if self._candidate_gesture == gesture:
            self._candidate_streak += 1
        else:
            self._candidate_gesture = gesture
            self._candidate_streak = 1

        return self._candidate_streak >= settings.GESTURE_HOLD_FRAMES

    def _handle_mute_gesture(self, thumb_point: Tuple[int, int],
                              index_point: Tuple[int, int]) -> GestureResult:
        """
        Requires a closed fist to be held for MUTE_HOLD_FRAMES consecutive
        frames, then respects a cooldown before allowing another toggle.
        This double safeguard prevents accidental mute/unmute flapping.
        """
        self._reset_streak()
        self._fist_streak += 1

        if self._fist_streak < settings.MUTE_HOLD_FRAMES:
            return GestureResult(
                Gesture.NONE, thumb_point=thumb_point, index_point=index_point,
                raw_label=f"MUTE (holding {self._fist_streak}/{settings.MUTE_HOLD_FRAMES})"
            )

        now = time.time()
        if now - self._last_mute_toggle_time < settings.MUTE_COOLDOWN:
            return GestureResult(
                Gesture.NONE, thumb_point=thumb_point, index_point=index_point,
                raw_label="MUTE (cooldown)"
            )

        self._last_mute_toggle_time = now
        self._fist_streak = 0
        return GestureResult(
            Gesture.MUTE_TOGGLE, thumb_point=thumb_point, index_point=index_point,
            raw_label="MUTE_TOGGLE"
        )
