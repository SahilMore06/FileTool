"""Unit tests for macOS Drag Detection state machine with fake inputs."""

from __future__ import annotations

from filetool.platform.mac_drag_monitor import (
    MASK_COMMAND,
    MASK_CONTROL,
    MASK_SHIFT,
    VK_ESCAPE,
    VK_RETURN,
    VK_RIGHT,
    DragStateMachine,
)


def test_mouse_down_and_movement_threshold():
    sm = DragStateMachine()
    fake_files = ["/Users/test/sample.jpg"]

    assert not sm.is_button_down
    assert not sm.is_file_drag

    events = sm.update(
        timestamp=1.0,
        left_down=True,
        flags=0,
        mouse_pos=(100.0, 100.0),
        pasteboard_change_count=10,
        get_files_fn=lambda: fake_files,
    )
    assert sm.is_button_down
    assert not sm.is_file_drag
    assert len(events) == 0

    events = sm.update(
        timestamp=1.05,
        left_down=True,
        flags=0,
        mouse_pos=(102.0, 100.0),
        pasteboard_change_count=11,
        get_files_fn=lambda: fake_files,
    )
    assert not sm.is_file_drag

    sm.mouse_down_change_count = 10
    events = sm.update(
        timestamp=1.1,
        left_down=True,
        flags=0,
        mouse_pos=(110.0, 100.0),
        pasteboard_change_count=10,
        get_files_fn=lambda: fake_files,
    )
    assert not sm.is_file_drag

    events = sm.update(
        timestamp=1.15,
        left_down=True,
        flags=0,
        mouse_pos=(110.0, 100.0),
        pasteboard_change_count=11,
        get_files_fn=lambda: fake_files,
    )
    assert sm.is_file_drag
    assert sm.dragged_files == fake_files


def test_shift_tap_triggers_convert_wheel():
    sm = DragStateMachine()
    fake_files = ["/Users/test/document.pdf"]

    # Activate file drag
    sm.update(1.0, True, 0, (100.0, 100.0), 1, lambda: fake_files)
    sm.update(1.05, True, 0, (120.0, 100.0), 2, lambda: fake_files)
    assert sm.is_file_drag

    # Shift key pressed down at t=1.1 -> triggers convert wheel immediately!
    events = sm.update(1.1, True, MASK_SHIFT, (122.0, 100.0), 2, lambda: fake_files)
    assert len(events) == 1
    assert events[0].event_type == "trigger"
    assert events[0].wheel_type == "convert"
    assert events[0].files == fake_files
    assert sm.wheel_open

    # Shift key released at t=1.25 -> wheel remains open!
    events = sm.update(1.25, True, 0, (125.0, 100.0), 2, lambda: fake_files)
    assert sm.wheel_open


def test_command_tap_triggers_tools_wheel():
    sm = DragStateMachine()
    fake_files = ["/Users/test/video.mp4"]

    # Activate file drag
    sm.update(1.0, True, 0, (100.0, 100.0), 1, lambda: fake_files)
    sm.update(1.05, True, 0, (120.0, 100.0), 2, lambda: fake_files)

    # Command down at t=2.0 -> triggers tools wheel immediately
    events = sm.update(2.0, True, MASK_COMMAND, (120.0, 100.0), 2, lambda: fake_files)
    assert len(events) == 1
    assert events[0].event_type == "trigger"
    assert events[0].wheel_type == "tools"
    assert sm.wheel_open


def test_control_tap_triggers_actions_wheel():
    sm = DragStateMachine()
    fake_files = ["/Users/test/archive.zip"]

    # Activate file drag
    sm.update(1.0, True, 0, (100.0, 100.0), 1, lambda: fake_files)
    sm.update(1.05, True, 0, (120.0, 100.0), 2, lambda: fake_files)

    # Control down at t=3.0 -> triggers actions wheel immediately
    events = sm.update(3.0, True, MASK_CONTROL, (120.0, 100.0), 2, lambda: fake_files)
    assert len(events) == 1
    assert events[0].event_type == "trigger"
    assert events[0].wheel_type == "actions"
    assert sm.wheel_open


def test_modifier_when_mouse_up_does_not_trigger():
    sm = DragStateMachine()
    fake_files = ["/Users/test/sample.png"]

    # Mouse is UP: pressing and releasing Shift should not open the wheel
    events = sm.update(1.0, False, MASK_SHIFT, (100.0, 100.0), 1, lambda: fake_files)
    assert len(events) == 0
    assert not sm.wheel_open

    events = sm.update(1.5, False, 0, (100.0, 100.0), 1, lambda: fake_files)
    assert len(events) == 0
    assert not sm.wheel_open


def test_multiple_modifiers_pressed_invalidates_tap():
    sm = DragStateMachine()
    fake_files = ["/Users/test/sample.png"]

    sm.update(1.0, True, 0, (100.0, 100.0), 1, lambda: fake_files)
    sm.update(1.05, True, 0, (120.0, 100.0), 2, lambda: fake_files)

    # Both Shift and Command pressed simultaneously
    sm.update(1.1, True, MASK_SHIFT | MASK_COMMAND, (120.0, 100.0), 2, lambda: fake_files)
    # Released at t=1.2
    events = sm.update(1.2, True, 0, (120.0, 100.0), 2, lambda: fake_files)
    assert len(events) == 0
    assert not sm.wheel_open


def test_wheel_switch_on_another_trigger():
    sm = DragStateMachine()
    fake_files = ["/Users/test/sample.png"]

    # Activate file drag and open convert wheel
    sm.update(1.0, True, 0, (100.0, 100.0), 1, lambda: fake_files)
    sm.update(1.05, True, 0, (120.0, 100.0), 2, lambda: fake_files)
    events = sm.update(1.1, True, MASK_SHIFT, (120.0, 100.0), 2, lambda: fake_files)
    assert len(events) == 1
    assert sm.wheel_open
    assert sm.active_wheel_type == "convert"
    sm.update(1.2, True, 0, (120.0, 100.0), 2, lambda: fake_files)

    # Now press Command while wheel is already open -> Switch to Tools wheel immediately!
    events = sm.update(1.3, True, MASK_COMMAND, (122.0, 100.0), 2, lambda: fake_files)
    switch_evs = [e for e in events if e.event_type == "switch"]
    assert len(switch_evs) == 1
    assert switch_evs[0].wheel_type == "tools"
    assert sm.active_wheel_type == "tools"


def test_mouse_release_while_wheel_open_emits_drop():
    sm = DragStateMachine()
    fake_files = ["/Users/test/sample.png"]

    # Open wheel
    sm.update(1.0, True, 0, (100.0, 100.0), 1, lambda: fake_files)
    sm.update(1.05, True, 0, (120.0, 100.0), 2, lambda: fake_files)
    sm.update(1.1, True, MASK_SHIFT, (120.0, 100.0), 2, lambda: fake_files)
    sm.update(1.2, True, 0, (120.0, 100.0), 2, lambda: fake_files)
    assert sm.wheel_open

    # Mouse button released at (250, 150)
    events = sm.update(1.3, False, 0, (250.0, 150.0), 2, lambda: fake_files)
    assert len(events) == 1
    assert events[0].event_type == "drop"
    assert events[0].position == (250.0, 150.0)
    assert events[0].wheel_type == "convert"
    assert not sm.wheel_open


def test_keyboard_events_while_wheel_open():
    sm = DragStateMachine()
    fake_files = ["/Users/test/sample.png"]

    # Open wheel
    sm.update(1.0, True, 0, (100.0, 100.0), 1, lambda: fake_files)
    sm.update(1.05, True, 0, (120.0, 100.0), 2, lambda: fake_files)
    sm.update(1.1, True, MASK_SHIFT, (120.0, 100.0), 2, lambda: fake_files)
    sm.update(1.2, True, 0, (120.0, 100.0), 2, lambda: fake_files)
    assert sm.wheel_open

    # Right arrow
    events = sm.update(
        1.3, True, 0, (120.0, 100.0), 2, lambda: fake_files, key_states={VK_RIGHT: True}
    )
    assert any(e.event_type == "nav" and e.direction == "right" for e in events)

    # Return key
    events = sm.update(
        1.4, True, 0, (120.0, 100.0), 2, lambda: fake_files, key_states={VK_RETURN: True}
    )
    assert any(e.event_type == "nav" and e.direction == "apply" for e in events)

    # Escape key -> cancels wheel
    events = sm.update(
        1.5, True, 0, (120.0, 100.0), 2, lambda: fake_files, key_states={VK_ESCAPE: True}
    )
    assert any(e.event_type == "cancel" for e in events)
    assert not sm.wheel_open


def test_drag_detected_when_finder_increments_change_count_during_idle():
    sm = DragStateMachine()
    fake_files = ["/Users/test/sample.docx"]

    sm.update(1.0, False, 0, (100.0, 100.0), 5, lambda: [])
    assert sm.last_idle_change_count == 5

    sm.update(1.1, True, 0, (100.0, 100.0), 6, lambda: fake_files)
    assert sm.mouse_down_change_count == 6
    assert not sm.is_file_drag

    events = sm.update(1.15, True, 0, (110.0, 100.0), 6, lambda: fake_files)
    assert sm.is_file_drag
    assert sm.dragged_files == fake_files


def test_modifier_tap_triggers_wheel_if_files_present_on_pasteboard():
    sm = DragStateMachine()
    fake_files = ["/Users/test/notes.txt"]

    sm.update(1.0, False, 0, (100.0, 100.0), 10, lambda: [])
    sm.update(1.1, True, 0, (100.0, 100.0), 11, lambda: fake_files)

    events = sm.update(1.15, True, MASK_SHIFT, (101.0, 100.0), 11, lambda: fake_files)
    assert len(events) == 1
    assert events[0].event_type == "trigger"
    assert events[0].wheel_type == "convert"
    assert sm.wheel_open


def test_sticky_mode_tracks_cursor_switches_wheel_and_preserves_files_on_click():
    sm = DragStateMachine()
    fake_files = ["/Users/test/photo.png"]

    sm.open_sticky_wheel("convert", (200.0, 200.0), fake_files)
    assert sm.wheel_open
    assert sm.sticky_mode
    assert sm.dragged_files == fake_files

    # Cursor movement with mouse button UP still emits "move" for live hover
    move_evs = sm.update(1.0, False, 0, (240.0, 140.0), 5, lambda: [])
    assert any(e.event_type == "move" and e.position == (240.0, 140.0) for e in move_evs)

    # Modifier press & release while mouse UP switches wheel cleanly
    sw_evs = sm.update(1.05, False, MASK_COMMAND, (240.0, 140.0), 5, lambda: [])
    assert any(e.event_type == "switch" and e.wheel_type == "tools" for e in sw_evs)
    assert sm.active_wheel_type == "tools"
    sm.update(1.10, False, 0, (240.0, 140.0), 5, lambda: [])
    assert sm.wheel_open

    # Clicking down on a petal must NOT wipe dragged_files; release emits drop with files
    sm.update(1.20, True, 0, (240.0, 140.0), 5, lambda: [])
    assert sm.dragged_files == fake_files
    drop_evs = sm.update(1.25, False, 0, (240.0, 140.0), 5, lambda: [])
    assert len(drop_evs) == 1
    assert drop_evs[0].event_type == "drop"
    assert drop_evs[0].wheel_type == "tools"
    assert drop_evs[0].files == fake_files


def test_keyboard_navigation_is_edge_triggered_per_press():
    sm = DragStateMachine()
    fake_files = ["/Users/test/photo.png"]
    sm.open_sticky_wheel("convert", (200.0, 200.0), fake_files)

    # Holding Right arrow across multiple ticks only emits once per key press
    e1 = sm.update(1.0, False, 0, (200.0, 200.0), 1, lambda: [], key_states={VK_RIGHT: True})
    e2 = sm.update(1.02, False, 0, (200.0, 200.0), 1, lambda: [], key_states={VK_RIGHT: True})
    assert sum(1 for e in e1 if e.event_type == "nav") == 1
    assert sum(1 for e in e2 if e.event_type == "nav") == 0

    # Release and press again emits again
    sm.update(1.04, False, 0, (200.0, 200.0), 1, lambda: [], key_states={VK_RIGHT: False})
    e3 = sm.update(1.06, False, 0, (200.0, 200.0), 1, lambda: [], key_states={VK_RIGHT: True})
    assert sum(1 for e in e3 if e.event_type == "nav") == 1

