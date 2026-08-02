"""
src/utils.py
============
Shared helper functions: geometry calculations and on-screen UI drawing.
Keeping these outside the main control loop keeps main.py focused and
readable.
"""

import math
from typing import Tuple

import cv2
import numpy as np

from config import settings


def calculate_distance(point_a: Tuple[int, int], point_b: Tuple[int, int]) -> float:
    """Euclidean distance between two 2D points."""
    return math.hypot(point_b[0] - point_a[0], point_b[1] - point_a[1])


def clamp(value: float, min_value: float, max_value: float) -> float:
    """Restrict a value to the inclusive range [min_value, max_value]."""
    return max(min_value, min(value, max_value))


def map_range(value: float, in_min: float, in_max: float,
              out_min: float, out_max: float) -> float:
    """Linearly map a value from one numeric range to another, clamped."""
    in_span = in_max - in_min
    if in_span == 0:
        return out_min
    scaled = (value - in_min) / in_span
    scaled = clamp(scaled, 0.0, 1.0)
    return out_min + (scaled * (out_max - out_min))


def draw_rounded_panel(frame: np.ndarray, top_left: Tuple[int, int],
                        bottom_right: Tuple[int, int],
                        color: Tuple[int, int, int],
                        alpha: float = 0.6) -> np.ndarray:
    """Draw a semi-transparent filled rectangle used as a UI backdrop."""
    overlay = frame.copy()
    cv2.rectangle(overlay, top_left, bottom_right, color, thickness=-1)
    return cv2.addWeighted(overlay, alpha, frame, 1 - alpha, 0)


def draw_status_panel(frame: np.ndarray, fps: float, webcam_ok: bool,
                       detection_confidence: float, mode: str,
                       is_muted: bool) -> np.ndarray:
    """
    Render the heads-up display: FPS counter, webcam status,
    detection confidence, current gesture mode, and mute state.
    """
    panel_height = 155
    frame = draw_rounded_panel(
        frame, (0, 0), (320, panel_height), settings.COLOR_PANEL_BG, alpha=0.55
    )

    # FPS
    fps_color = settings.COLOR_SUCCESS if fps >= 15 else settings.COLOR_WARNING
    cv2.putText(frame, f"FPS: {fps:.1f}", (12, 28),
                cv2.FONT_HERSHEY_SIMPLEX, 0.65, fps_color, 2)

    # Webcam status
    status_text = "Webcam: ONLINE" if webcam_ok else "Webcam: OFFLINE"
    status_color = settings.COLOR_SUCCESS if webcam_ok else settings.COLOR_ERROR
    cv2.putText(frame, status_text, (12, 56),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, status_color, 2)

    # Detection confidence
    cv2.putText(frame, f"Detection Conf: {detection_confidence:.2f}",
                (12, 84), cv2.FONT_HERSHEY_SIMPLEX, 0.55,
                settings.COLOR_TEXT, 1)

    # Current gesture / mode
    cv2.putText(frame, f"Mode: {mode}", (12, 112),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, settings.COLOR_PRIMARY, 2)

    # Mute indicator
    mute_text = "Audio: MUTED" if is_muted else "Audio: UNMUTED"
    mute_color = settings.COLOR_MUTED if is_muted else settings.COLOR_SUCCESS
    cv2.putText(frame, mute_text, (12, 140),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, mute_color, 2)

    return frame


def draw_exit_hint(frame: np.ndarray) -> np.ndarray:
    """Render the keyboard shortcut hint in the bottom-left corner."""
    h, _ = frame.shape[:2]
    text = f"Press '{settings.EXIT_KEY.upper()}' or ESC to exit safely"
    cv2.putText(frame, text, (12, h - 16),
                cv2.FONT_HERSHEY_SIMPLEX, 0.55, settings.COLOR_TEXT, 1)
    return frame


def draw_volume_bar(frame: np.ndarray, volume_percent: float,
                     is_muted: bool) -> np.ndarray:
    """
    Draws a dynamic, vertical volume bar and its live percentage label
    on the right-hand side of the frame.
    """
    h, w = frame.shape[:2]
    bar_x = w - settings.VOLUME_BAR_X - settings.VOLUME_BAR_WIDTH
    top_y = settings.VOLUME_BAR_TOP_Y
    bottom_y = settings.VOLUME_BAR_BOTTOM_Y
    bar_width = settings.VOLUME_BAR_WIDTH

    # Outer bar outline
    cv2.rectangle(frame, (bar_x, top_y), (bar_x + bar_width, bottom_y),
                  settings.COLOR_TEXT, 2)

    # Filled portion, proportional to current volume
    fill_height = int(map_range(volume_percent, 0, 100, 0, bottom_y - top_y))
    fill_top_y = bottom_y - fill_height

    fill_color = settings.COLOR_MUTED if is_muted else settings.COLOR_SUCCESS
    cv2.rectangle(frame, (bar_x, fill_top_y), (bar_x + bar_width, bottom_y),
                  fill_color, cv2.FILLED)

    # Percentage label above the bar
    label = "MUTED" if is_muted else f"{int(volume_percent)}%"
    cv2.putText(frame, label, (bar_x - 15, top_y - 15),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, settings.COLOR_TEXT, 2)

    return frame


def draw_pinch_line(frame: np.ndarray, point_a: Tuple[int, int],
                     point_b: Tuple[int, int], distance: float) -> np.ndarray:
    """Draws the thumb-index control line with endpoint markers."""
    cv2.circle(frame, point_a, 10, settings.COLOR_PRIMARY, cv2.FILLED)
    cv2.circle(frame, point_b, 10, settings.COLOR_PRIMARY, cv2.FILLED)
    cv2.line(frame, point_a, point_b, settings.COLOR_PRIMARY, 3)

    mid_point = ((point_a[0] + point_b[0]) // 2, (point_a[1] + point_b[1]) // 2)
    line_color = settings.COLOR_SUCCESS if distance > settings.HAND_DISTANCE_MIN + 15 \
        else settings.COLOR_ERROR
    cv2.circle(frame, mid_point, 8, line_color, cv2.FILLED)

    return frame
