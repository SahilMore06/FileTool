"""macOS platform integrations: drag monitor, window management, actions."""

import sys
import platform

from filetool.platform.mac_drag_monitor import MacDragMonitor, DragStateMachine
from filetool.platform.mac_actions import (
    trigger_haptic_tick,
    reveal_in_finder,
    send_completion_notification,
    action_airdrop,
    action_copy_files,
    action_copy_path,
    action_float,
    action_move_files,
    action_open_in_terminal,
    is_launch_at_login_enabled,
    set_launch_at_login,
)
from filetool.platform.mac_window import (
    configure_overlay_window,
    show_without_activating,
    clamp_window_to_screen,
    mac_screen_to_qt_coords,
)

# Bridge for top-level `platform.mac_...` imports without shadowing standard library platform
import filetool.platform.mac_drag_monitor as _mdm
import filetool.platform.mac_actions as _ma
import filetool.platform.mac_window as _mw

sys.modules["platform.mac_drag_monitor"] = _mdm
sys.modules["platform.mac_actions"] = _ma
sys.modules["platform.mac_window"] = _mw
setattr(platform, "mac_drag_monitor", _mdm)
setattr(platform, "mac_actions", _ma)
setattr(platform, "mac_window", _mw)

__all__ = [
    "MacDragMonitor",
    "DragStateMachine",
    "trigger_haptic_tick",
    "reveal_in_finder",
    "send_completion_notification",
    "action_airdrop",
    "action_copy_files",
    "action_copy_path",
    "action_float",
    "action_move_files",
    "action_open_in_terminal",
    "is_launch_at_login_enabled",
    "set_launch_at_login",
    "configure_overlay_window",
    "show_without_activating",
    "clamp_window_to_screen",
    "mac_screen_to_qt_coords",
]
