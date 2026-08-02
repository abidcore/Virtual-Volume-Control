"""
config/settings.py
===================
Centralized configuration for the AI Virtual Volume Control System.

Keeping every tunable parameter in a single module makes the application
easy to calibrate for different cameras, hand sizes, and user preferences
without touching the core logic in `src/`.
"""

# ---------------------------------------------------------------------------
# Camera Configuration
# ---------------------------------------------------------------------------
CAMERA_INDEX = 0                 # Default webcam device index
FRAME_WIDTH = 640                 # Capture frame width (pixels)
FRAME_HEIGHT = 480                # Capture frame height (pixels)
FLIP_CAMERA = True                # Mirror the webcam feed for a natural UX

# ---------------------------------------------------------------------------
# MediaPipe Hand Detection Configuration
# ---------------------------------------------------------------------------
MAX_NUM_HANDS = 1                  # Track a single hand for stable control
MIN_DETECTION_CONFIDENCE = 0.75    # Minimum confidence to detect a hand
MIN_TRACKING_CONFIDENCE = 0.75     # Minimum confidence to keep tracking a hand
MODEL_COMPLEXITY = 1               # 0 = lite, 1 = full (accuracy/speed trade-off)

# ---------------------------------------------------------------------------
# Volume Gesture Mapping
# ---------------------------------------------------------------------------
# Thumb-to-index fingertip pixel distance range that maps to 0% - 100%
# system volume. Calibrated for a hand roughly 30-50cm from a 640x480 feed;
# adjust if your camera resolution or typical hand distance differs.
HAND_DISTANCE_MIN = 25            # px -> maps to 0% volume (pinched closed)
HAND_DISTANCE_MAX = 200           # px -> maps to 100% volume (fingers spread)

# ---------------------------------------------------------------------------
# Smoothing & Gesture Stabilization
# ---------------------------------------------------------------------------
# Raw fingertip distance is noisy frame-to-frame due to landmark jitter.
# A rolling average over this many recent samples stabilizes the reading
# before it is converted into a volume percentage.
STABILIZATION_WINDOW = 5

# Exponential Moving Average factor applied to the final volume percentage
# before it is sent to the OS mixer. Lower = smoother but slightly laggier
# transitions. Higher = snappier but less smooth.
VOLUME_SMOOTHING_FACTOR = 0.25

# Minimum change in volume percentage required before we bother issuing a
# new OS-level volume-set call (reduces redundant system calls).
VOLUME_UPDATE_THRESHOLD = 0.5

# ---------------------------------------------------------------------------
# Gesture Recognition Timing
# ---------------------------------------------------------------------------
GESTURE_HOLD_FRAMES = 3           # Frames required to confirm entering
                                   # "volume control" mode (debounce)
MUTE_HOLD_FRAMES = 15             # Frames a closed fist must be held to
                                   # trigger a mute/unmute toggle
MUTE_COOLDOWN = 1.0                # seconds between mute-toggle events

# ---------------------------------------------------------------------------
# UI / Overlay Configuration
# ---------------------------------------------------------------------------
SHOW_FPS = True
SHOW_LANDMARKS = True
SHOW_STATUS_PANEL = True

WINDOW_NAME = "AI Virtual Volume Control System"

# Volume bar geometry (pixels, relative to the frame)
VOLUME_BAR_X = 50
VOLUME_BAR_TOP_Y = 150
VOLUME_BAR_BOTTOM_Y = 400
VOLUME_BAR_WIDTH = 35

# Colors are defined in BGR (OpenCV convention)
COLOR_PRIMARY = (255, 0, 200)
COLOR_SUCCESS = (0, 220, 0)
COLOR_WARNING = (0, 165, 255)
COLOR_ERROR = (0, 0, 255)
COLOR_TEXT = (255, 255, 255)
COLOR_PANEL_BG = (30, 30, 30)
COLOR_MUTED = (0, 0, 255)

# ---------------------------------------------------------------------------
# Application Behaviour
# ---------------------------------------------------------------------------
EXIT_KEY = "q"                     # Keyboard shortcut to quit safely (ESC also works)
