"""macOS platform integrations: drag monitor, window management, actions."""

from filetool.platform.mac_drag_monitor import MacDragMonitor, DragStateMachine
from filetool.platform.mac_actions import (
    play_tactile_feedback,
    trigger_haptic_sequence,
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

__all__ = [
    "MacDragMonitor",
    "DragStateMachine",
    "play_tactile_feedback",
    "trigger_haptic_sequence",
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
