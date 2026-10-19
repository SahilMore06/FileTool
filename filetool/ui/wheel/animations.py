"""Animation timing constants, curves, and macOS Reduce Motion handling."""

from __future__ import annotations

import logging
import math

logger = logging.getLogger("filetool.ui.wheel.animations")

# --- Tunable Animation Constants (60 fps) ---

# 1. Open Animation
OPEN_DURATION_MS: int = 180
OPEN_START_SCALE: float = 0.7
OPEN_OVERSHOOT_SCALE: float = 1.04
OPEN_END_SCALE: float = 1.0
STAGGER_INTERVAL_MS: int = 12  # Clockwise delay per segment

# 2. Hover Animation
HOVER_DURATION_MS: int = 90
HOVER_SCALE: float = 1.06
HOVER_BRIGHTNESS: float = 1.25

# 3. Wheel Switch Animation
SWITCH_DURATION_MS: int = 150
SWITCH_ROTATION_DEG: float = 14.0

# 4. Drop & Execution Animation
DROP_FLASH_DURATION_MS: int = 80
DROP_COLLAPSE_DURATION_MS: int = 150
PROGRESS_UPDATE_INTERVAL_MS: int = 16  # 60 Hz progress ring update

# 5. Result Animations
DONE_DURATION_MS: int = 400
ERROR_SHAKE_DURATION_MS: int = 250
ERROR_SHAKE_AMPLITUDE_PX: float = 8.0

# 6. Cancel Animation
CANCEL_DURATION_MS: int = 120
CANCEL_END_SCALE: float = 0.8


def should_reduce_motion() -> bool:
    """Check if macOS has 'Reduce Motion' enabled in Accessibility settings."""
    try:
        from AppKit import NSWorkspace
        ws = NSWorkspace.sharedWorkspace()
        if hasattr(ws, "accessibilityDisplayShouldReduceMotion"):
            return bool(ws.accessibilityDisplayShouldReduceMotion())
    except Exception as exc:
        logger.debug("Failed checking reduce motion setting: %s", exc)
    return False


def ease_out_back(t: float, overshoot: float = 1.2) -> float:
    """Overshoot spring easing: t in [0.0, 1.0]."""
    if t <= 0.0:
        return 0.0
    if t >= 1.0:
        return 1.0
    t -= 1.0
    return t * t * ((overshoot + 1.0) * t + overshoot) + 1.0


def ease_out_quad(t: float) -> float:
    """Smooth deceleration curve."""
    t = max(0.0, min(1.0, t))
    return t * (2.0 - t)


def ease_in_out_quad(t: float) -> float:
    """Smooth acceleration and deceleration."""
    t = max(0.0, min(1.0, t))
    if t < 0.5:
        return 2.0 * t * t
    return -1.0 + (4.0 - 2.0 * t) * t


def shake_offset(t: float, amplitude: float = ERROR_SHAKE_AMPLITUDE_PX) -> float:
    """Calculate horizontal pixel shake offset for error animation."""
    t = max(0.0, min(1.0, t))
    # Decay envelope: (1 - t)
    decay = 1.0 - t
    # 3.5 cycles of sine wave
    return math.sin(t * math.pi * 7.0) * amplitude * decay
