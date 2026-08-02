"""
main.py
=======
Entry point for the AI Virtual Volume Control System.

Captures webcam video, runs real-time hand tracking, converts the
tracked thumb-index finger distance into a smoothed system volume
level, and renders a live heads-up display with a dynamic volume bar.

Run this file directly to start the application:

    python main.py

Press 'Q' (or ESC) in the video window to exit safely at any time.
"""

import sys
import time

import cv2

from config import settings
from src.hand_tracker import HandTracker
from src.gesture_detector import GestureDetector, Gesture
from src.volume_controller import VolumeController
from src.fps import FPSCounter
from src.utils import (
    draw_status_panel,
    draw_exit_hint,
    draw_volume_bar,
    draw_pinch_line,
)


class VirtualVolumeApp:
    """Top-level application object: owns the main capture/processing loop."""

    def __init__(self) -> None:
        self.capture = None
        self.tracker = HandTracker()
        self.gesture_detector = GestureDetector(self.tracker)
        self.volume_controller = VolumeController()
        self.fps_counter = FPSCounter()
        self.webcam_ok = False

    # ------------------------------------------------------------------
    # Setup
    # ------------------------------------------------------------------
    def _open_camera(self) -> None:
        """Open the webcam and configure its resolution, with error handling."""
        self.capture = cv2.VideoCapture(settings.CAMERA_INDEX)

        if not self.capture.isOpened():
            raise RuntimeError(
                f"Could not open webcam at index {settings.CAMERA_INDEX}. "
                "Check that a camera is connected, that no other "
                "application is using it, and that OS camera permissions "
                "are granted."
            )

        self.capture.set(cv2.CAP_PROP_FRAME_WIDTH, settings.FRAME_WIDTH)
        self.capture.set(cv2.CAP_PROP_FRAME_HEIGHT, settings.FRAME_HEIGHT)
        self.webcam_ok = True

    # ------------------------------------------------------------------
    # Main loop
    # ------------------------------------------------------------------
    def run(self) -> None:
        """Starts the application and runs until the user exits."""
        try:
            self._open_camera()
        except RuntimeError as error:
            print(f"[FATAL] {error}")
            sys.exit(1)

        print("=" * 60)
        print(" AI Virtual Volume Control System - Started")
        print("=" * 60)
        print(f" Press '{settings.EXIT_KEY.upper()}' (or ESC) in the video "
              "window to exit safely.")
        print(" Gestures:")
        print("   Thumb + Index finger only  -> Control volume (distance = level)")
        print("   Closed fist (hold ~0.5s)   -> Toggle mute / unmute")
        if self.volume_controller.is_simulated:
            print(" NOTE: Real system audio control is unavailable on this")
            print("       platform (Pycaw requires Windows). Running in")
            print("       simulation mode - the UI will still respond live.")
        print("=" * 60)

        try:
            while True:
                success, frame = self.capture.read()

                if not success or frame is None:
                    self.webcam_ok = False
                    print("[WARNING] Failed to read frame from webcam. Retrying...")
                    time.sleep(0.1)
                    continue

                self.webcam_ok = True

                if settings.FLIP_CAMERA:
                    frame = cv2.flip(frame, 1)

                frame = self._process_frame(frame)

                cv2.imshow(settings.WINDOW_NAME, frame)

                key = cv2.waitKey(1) & 0xFF
                if key == ord(settings.EXIT_KEY) or key == 27:  # 27 = ESC key
                    print("Exit key pressed. Shutting down safely.")
                    break

                # Allow safe exit if the user closes the window directly.
                if cv2.getWindowProperty(
                    settings.WINDOW_NAME, cv2.WND_PROP_VISIBLE
                ) < 1:
                    print("Window closed. Shutting down safely.")
                    break

        except KeyboardInterrupt:
            print("\nInterrupted by user (Ctrl+C). Shutting down safely.")
        except Exception as error:  # noqa: BLE001 - top-level safety net
            print(f"[ERROR] Unexpected failure: {error}")
        finally:
            self._cleanup()

    # ------------------------------------------------------------------
    # Per-frame processing
    # ------------------------------------------------------------------
    def _process_frame(self, frame):
        """Runs detection, gesture recognition, and volume control for one frame."""
        frame = self.tracker.find_hands(frame, draw=settings.SHOW_LANDMARKS)
        landmarks = self.tracker.find_positions(frame)

        result = self.gesture_detector.detect(landmarks)
        self._dispatch_gesture(result, frame)

        is_muted = self.volume_controller.is_muted()
        current_percent = self.volume_controller.get_current_percent()
        frame = draw_volume_bar(frame, current_percent, is_muted)

        if settings.SHOW_STATUS_PANEL:
            fps = self.fps_counter.update()
            frame = draw_status_panel(
                frame,
                fps=fps,
                webcam_ok=self.webcam_ok,
                detection_confidence=self.tracker.last_detection_confidence,
                mode=result.raw_label,
                is_muted=is_muted,
            )

        frame = draw_exit_hint(frame)
        return frame

    def _dispatch_gesture(self, result, frame) -> None:
        """Maps a GestureResult onto the appropriate VolumeController call."""
        if result.gesture == Gesture.VOLUME_CONTROL:
            self.volume_controller.set_volume_from_distance(result.distance)
            if settings.SHOW_LANDMARKS:
                draw_pinch_line(frame, result.thumb_point, result.index_point,
                                 result.distance)
        elif result.gesture == Gesture.MUTE_TOGGLE:
            self.volume_controller.toggle_mute()

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------
    def _cleanup(self) -> None:
        """Releases all camera, window, and MediaPipe resources."""
        if self.capture is not None:
            self.capture.release()
        cv2.destroyAllWindows()
        self.tracker.close()
        print("Resources released. Goodbye!")


if __name__ == "__main__":
    app = VirtualVolumeApp()
    app.run()
