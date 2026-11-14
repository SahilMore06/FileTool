"""Animation timing constants, curves, and macOS Reduce Motion handling."""

from __future__ import annotations

import logging
import math

logger = logging.getLogger("filetool.ui.wheel.animations")

OPEN_DURATION_MS: int = 115
OPEN_START_SCALE: float = 0.78
OPEN_OVERSHOOT_SCALE: float = 1.04
OPEN_END_SCALE: float = 1.0
STAGGER_INTERVAL_MS: int = 6

HOVER_DURATION_MS: int = 50
HOVER_SCALE: float = 1.06

SWITCH_DURATION_MS: int = 105
SWITCH_ROTATION_DEG: float = 14.0

DROP_FLASH_DURATION_MS: int = 50
DROP_COLLAPSE_DURATION_MS: int = 100

DONE_DURATION_MS: int = 360
ERROR_SHAKE_DURATION_MS: int = 220
ERROR_SHAKE_AMPLITUDE_PX: float = 8.0

CANCEL_DURATION_MS: int = 85
CANCEL_END_SCALE: float = 0.82

_SHARED_WORKSPACE = None
_WORKSPACE_INIT = False


def should_reduce_motion() -> bool:
    """Check if macOS has 'Reduce Motion' enabled in Accessibility settings."""
    global _SHARED_WORKSPACE, _WORKSPACE_INIT
    if not _WORKSPACE_INIT:
        _WORKSPACE_INIT = True
        try:
            from AppKit import NSWorkspace
            _SHARED_WORKSPACE = NSWorkspace.sharedWorkspace()
        except Exception as exc:
            logger.debug("Failed initializing NSWorkspace for reduce motion: %s", exc)
            _SHARED_WORKSPACE = None
    ws = _SHARED_WORKSPACE
    if ws is not None:
        try:
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


def shake_offset(t: float, amplitude: float = ERROR_SHAKE_AMPLITUDE_PX) -> float:
    """Compute decaying horizontal sinusoidal shake offset for error feedback."""
    t = max(0.0, min(1.0, t))
    decay = 1.0 - t
    return math.sin(t * math.pi * 7.0) * amplitude * decay
