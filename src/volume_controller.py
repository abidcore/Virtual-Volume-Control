"""
src/volume_controller.py
==========================
Owns all interaction with the operating system's audio mixer via Pycaw
(a Python wrapper around the Windows Core Audio APIs) and comtypes.

Responsibilities
-----------------
- Map a stabilized thumb-index pixel distance to a 0-100 volume
  percentage.
- Apply an Exponential Moving Average (EMA) filter so the actual system
  volume transitions smoothly rather than jumping between raw readings.
- Push the smoothed percentage to the OS mixer, only issuing a new
  system call when the change is meaningful (VOLUME_UPDATE_THRESHOLD).
- Provide mute/unmute/toggle-mute controls.

Platform note
-------------
Pycaw wraps the Windows Core Audio API and therefore only functions on
Windows. To keep this module importable and demonstrable on any
development machine (macOS/Linux included), initialization failures are
caught and the controller transparently falls back to a "simulated"
in-memory mode: all public methods still work and the on-screen UI
still reflects volume changes, but no real system audio is touched.
This keeps the application runnable end-to-end for development, testing,
and demonstration purposes even outside Windows, while providing full,
real system-volume control when run on Windows with a valid audio
endpoint.
"""

from typing import Tuple

from config import settings
from src.utils import map_range, clamp

try:
    from ctypes import cast, POINTER
    from comtypes import CLSCTX_ALL
    from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume

    _PYCAW_IMPORT_OK = True
except Exception:  # pragma: no cover - exercised only on non-Windows hosts
    _PYCAW_IMPORT_OK = False


class VolumeController:
    """Owns mapping, smoothing, and OS-level audio volume control."""

    def __init__(self) -> None:
        self._simulated = False
        self._simulated_percent = 50.0
        self._simulated_muted = False

        self._endpoint_volume = None
        self._volume_range_db: Tuple[float, float] = (-65.25, 0.0)

        self._smoothed_percent: float = 50.0
        self._last_applied_percent: float = 50.0

        self._initialize_endpoint()

    # ------------------------------------------------------------------
    # Initialization
    # ------------------------------------------------------------------
    def _initialize_endpoint(self) -> None:
        """
        Attempts to bind to the default Windows audio output endpoint.
        Falls back to simulated mode on any failure (e.g. non-Windows OS,
        no active audio device, or a COM initialization error), printing
        a clear, one-time warning rather than crashing the application.
        """
        if not _PYCAW_IMPORT_OK:
            self._enable_simulation_mode(
                "Pycaw/comtypes are unavailable on this platform "
                "(Pycaw requires Windows)."
            )
            return

        try:
            devices = AudioUtilities.GetSpeakers()
            interface = devices.Activate(
                IAudioEndpointVolume._iid_, CLSCTX_ALL, None
            )
            self._endpoint_volume = cast(interface, POINTER(IAudioEndpointVolume))
            self._volume_range_db = self._endpoint_volume.GetVolumeRange()[:2]

            current_scalar = self._endpoint_volume.GetMasterVolumeLevelScalar()
            self._smoothed_percent = current_scalar * 100.0
            self._last_applied_percent = self._smoothed_percent
        except Exception as error:  # pragma: no cover
            self._enable_simulation_mode(
                f"Could not initialize the system audio endpoint ({error})."
            )

    def _enable_simulation_mode(self, reason: str) -> None:
        self._simulated = True
        print("=" * 60)
        print("[WARNING] Running VolumeController in SIMULATION mode.")
        print(f"          Reason: {reason}")
        print("          Real system volume will NOT be changed. The UI")
        print("          will still reflect gesture-driven volume levels.")
        print("=" * 60)

    # ------------------------------------------------------------------
    # Distance -> Volume mapping
    # ------------------------------------------------------------------
    @staticmethod
    def distance_to_percent(distance: float) -> float:
        """Maps a stabilized thumb-index pixel distance to 0-100%."""
        percent = map_range(
            distance,
            settings.HAND_DISTANCE_MIN,
            settings.HAND_DISTANCE_MAX,
            0.0,
            100.0,
        )
        return clamp(percent, 0.0, 100.0)

    # ------------------------------------------------------------------
    # Public volume actions
    # ------------------------------------------------------------------
    def set_volume_from_distance(self, distance: float) -> float:
        """
        Converts a stabilized distance into a target percentage, applies
        EMA smoothing for a fluid transition, and (if the change is
        meaningful) pushes the new level to the OS mixer.

        Returns the current smoothed percentage, for UI rendering.
        """
        target_percent = self.distance_to_percent(distance)

        factor = settings.VOLUME_SMOOTHING_FACTOR
        self._smoothed_percent = (
            self._smoothed_percent + (target_percent - self._smoothed_percent) * factor
        )

        if abs(self._smoothed_percent - self._last_applied_percent) >= \
                settings.VOLUME_UPDATE_THRESHOLD:
            self._apply_volume(self._smoothed_percent)
            self._last_applied_percent = self._smoothed_percent

        return self._smoothed_percent

    def _apply_volume(self, percent: float) -> None:
        """Pushes a 0-100 percentage to the real or simulated audio mixer."""
        percent = clamp(percent, 0.0, 100.0)

        if self._simulated:
            self._simulated_percent = percent
            return

        try:
            scalar = percent / 100.0
            self._endpoint_volume.SetMasterVolumeLevelScalar(scalar, None)
        except Exception as error:  # pragma: no cover
            print(f"[ERROR] Failed to set system volume: {error}")

    def get_current_percent(self) -> float:
        """Returns the current (smoothed) volume percentage for the UI."""
        if self._simulated:
            return self._simulated_percent
        return self._smoothed_percent

    # ------------------------------------------------------------------
    # Mute controls
    # ------------------------------------------------------------------
    def toggle_mute(self) -> bool:
        """Toggles mute state. Returns the new muted state (True = muted)."""
        if self._simulated:
            self._simulated_muted = not self._simulated_muted
            return self._simulated_muted

        try:
            currently_muted = bool(self._endpoint_volume.GetMute())
            self._endpoint_volume.SetMute(not currently_muted, None)
            return not currently_muted
        except Exception as error:  # pragma: no cover
            print(f"[ERROR] Failed to toggle mute: {error}")
            return False

    def is_muted(self) -> bool:
        """Returns whether audio is currently muted."""
        if self._simulated:
            return self._simulated_muted

        try:
            return bool(self._endpoint_volume.GetMute())
        except Exception:  # pragma: no cover
            return False

    @property
    def is_simulated(self) -> bool:
        """True if running without real OS audio access (non-Windows/dev)."""
        return self._simulated
