"""
src/hand_tracker.py
====================
Wraps Google's MediaPipe Hands solution behind a clean, reusable
interface so the rest of the application never has to touch the
MediaPipe API directly.
"""

from typing import List, Tuple, Optional

import cv2
import mediapipe as mp
import numpy as np

from config import settings


class HandTracker:
    """Detects a hand in a video frame and exposes its landmarks."""

    # MediaPipe landmark indices for finger tips and their corresponding
    # "pip" (proximal interphalangeal) joints, used for up/down checks.
    TIP_IDS = [4, 8, 12, 16, 20]      # thumb, index, middle, ring, pinky
    PIP_IDS = [2, 6, 10, 14, 18]

    def __init__(self) -> None:
        self._mp_hands = mp.solutions.hands
        self._hands = self._mp_hands.Hands(
            static_image_mode=False,
            max_num_hands=settings.MAX_NUM_HANDS,
            model_complexity=settings.MODEL_COMPLEXITY,
            min_detection_confidence=settings.MIN_DETECTION_CONFIDENCE,
            min_tracking_confidence=settings.MIN_TRACKING_CONFIDENCE,
        )
        self._mp_draw = mp.solutions.drawing_utils
        self._mp_styles = mp.solutions.drawing_styles

        self._results = None
        self.last_detection_confidence: float = 0.0

    def find_hands(self, frame: np.ndarray, draw: bool = True) -> np.ndarray:
        """
        Run hand detection on a BGR frame and optionally draw the
        skeleton overlay. Returns the (possibly annotated) frame.
        """
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        rgb_frame.flags.writeable = False
        self._results = self._hands.process(rgb_frame)
        rgb_frame.flags.writeable = True

        if self._results.multi_hand_landmarks:
            # MediaPipe does not expose a simple per-frame scalar confidence
            # once a hand is being tracked, so we use the handedness
            # classification score (when available) as a representative,
            # user-facing confidence readout.
            confidence = settings.MIN_DETECTION_CONFIDENCE
            if self._results.multi_handedness:
                confidence = self._results.multi_handedness[0].classification[0].score
            self.last_detection_confidence = confidence

            if draw:
                for hand_landmarks in self._results.multi_hand_landmarks:
                    self._mp_draw.draw_landmarks(
                        frame,
                        hand_landmarks,
                        self._mp_hands.HAND_CONNECTIONS,
                        self._mp_styles.get_default_hand_landmarks_style(),
                        self._mp_styles.get_default_hand_connections_style(),
                    )
        else:
            self.last_detection_confidence = 0.0

        return frame

    def find_positions(self, frame: np.ndarray,
                        hand_no: int = 0) -> List[Tuple[int, int, int]]:
        """
        Returns a list of (id, x, y) pixel coordinates for every
        landmark of the requested hand. Empty list if no hand is found.
        """
        landmark_list: List[Tuple[int, int, int]] = []

        if not self._results or not self._results.multi_hand_landmarks:
            return landmark_list

        if hand_no >= len(self._results.multi_hand_landmarks):
            return landmark_list

        hand = self._results.multi_hand_landmarks[hand_no]
        height, width = frame.shape[:2]

        for landmark_id, landmark in enumerate(hand.landmark):
            pixel_x, pixel_y = int(landmark.x * width), int(landmark.y * height)
            landmark_list.append((landmark_id, pixel_x, pixel_y))

        return landmark_list

    def fingers_up(self, landmark_list: List[Tuple[int, int, int]]) -> List[int]:
        """
        Determines which fingers are currently extended.

        Returns a list of 5 binary flags in the order
        [thumb, index, middle, ring, pinky], where 1 = extended, 0 = curled.
        """
        if not landmark_list or len(landmark_list) < 21:
            return [0, 0, 0, 0, 0]

        fingers = []
        points = {lm_id: (x, y) for lm_id, x, y in landmark_list}

        # Thumb: compare x-coordinates (valid for an upright hand facing
        # a mirrored/flipped camera feed).
        if points[self.TIP_IDS[0]][0] > points[self.PIP_IDS[0]][0]:
            fingers.append(1)
        else:
            fingers.append(0)

        # Remaining four fingers: tip above pip joint (smaller y = higher
        # on screen, since image y-coordinates increase downward).
        for tip_id, pip_id in zip(self.TIP_IDS[1:], self.PIP_IDS[1:]):
            if points[tip_id][1] < points[pip_id][1]:
                fingers.append(1)
            else:
                fingers.append(0)

        return fingers

    def find_distance(self, id_a: int, id_b: int,
                       landmark_list: List[Tuple[int, int, int]]) -> Optional[float]:
        """Euclidean pixel distance between two landmarks, or None."""
        points = {lm_id: (x, y) for lm_id, x, y in landmark_list}
        if id_a not in points or id_b not in points:
            return None

        ax, ay = points[id_a]
        bx, by = points[id_b]
        return float(np.hypot(bx - ax, by - ay))

    def close(self) -> None:
        """Release MediaPipe resources. Call this on application shutdown."""
        self._hands.close()
