"""Unit tests for radial wheel angle calculations, segment layout, and hit-testing."""

from __future__ import annotations

import math
import pytest

from filetool.ui.wheel.geometry import (
    HUB_RADIUS,
    RING1_INNER_RADIUS,
    RING1_OUTER_RADIUS,
    RING2_INNER_RADIUS,
    RING2_OUTER_RADIUS,
    HitResult,
    SegmentArc,
    clock_degrees_to_cartesian,
    hit_test,
    layout_segments,
    navigate_direction,
    point_to_clock_degrees,
)


def test_point_to_clock_degrees():
    # Top (12 o'clock)
    assert point_to_clock_degrees(0.0, -10.0) == pytest.approx(0.0, abs=1e-3)
    # Right (3 o'clock)
    assert point_to_clock_degrees(10.0, 0.0) == pytest.approx(90.0, abs=1e-3)
    # Bottom (6 o'clock)
    assert point_to_clock_degrees(0.0, 10.0) == pytest.approx(180.0, abs=1e-3)
    # Left (9 o'clock)
    assert point_to_clock_degrees(-10.0, 0.0) == pytest.approx(270.0, abs=1e-3)
    # Diagonals
    assert point_to_clock_degrees(10.0, -10.0) == pytest.approx(45.0, abs=1e-3)
    assert point_to_clock_degrees(-10.0, -10.0) == pytest.approx(315.0, abs=1e-3)


def test_clock_degrees_to_cartesian():
    r = 100.0
    # Top (0°) -> (0, -100)
    x, y = clock_degrees_to_cartesian(0.0, r)
    assert x == pytest.approx(0.0, abs=1e-3)
    assert y == pytest.approx(-100.0, abs=1e-3)

    # Right (90°) -> (100, 0)
    x, y = clock_degrees_to_cartesian(90.0, r)
    assert x == pytest.approx(100.0, abs=1e-3)
    assert y == pytest.approx(0.0, abs=1e-3)


def test_layout_segments_4_items():
    items = [
        {"label": "TOP", "icon": "top"},
        {"label": "RIGHT", "icon": "right"},
        {"label": "BOTTOM", "icon": "bottom"},
        {"label": "LEFT", "icon": "left"},
    ]
    segs = layout_segments(items, ring=1)
    assert len(segs) == 4

    assert segs[0].mid_angle == pytest.approx(0.0)
    assert segs[1].mid_angle == pytest.approx(90.0)
    assert segs[2].mid_angle == pytest.approx(180.0)
    assert segs[3].mid_angle == pytest.approx(270.0)

    # Centroid checks
    mid_r = (RING1_INNER_RADIUS + RING1_OUTER_RADIUS) / 2.0
    cx0, cy0 = segs[0].centroid
    assert cx0 == pytest.approx(0.0, abs=1e-2)
    assert cy0 == pytest.approx(-mid_r, abs=1e-2)


def test_hit_test_hub():
    items = [{"label": f"FMT_{i}"} for i in range(4)]
    segs = layout_segments(items)

    # Center (0, 0)
    res = hit_test(0.0, 0.0, segs)
    assert res.hit_type == "hub"

    # Edge of hub (radius 30)
    res = hit_test(20.0, 20.0, segs)
    assert res.hit_type == "hub"

    # In deadband / inner hub (radius 40 < 48.64)
    res = hit_test(0.0, -40.0, segs)
    assert res.hit_type == "hub"


def test_hit_test_primary_segments():
    items = [
        {"label": "TOP"},
        {"label": "RIGHT"},
        {"label": "BOTTOM"},
        {"label": "LEFT"},
    ]
    segs = layout_segments(items)
    mid_r = 100.0  # inside [RING1_INNER_RADIUS, RING1_OUTER_RADIUS]

    # Hit top segment (0)
    res_top = hit_test(0.0, -mid_r, segs)
    assert res_top.hit_type == "segment"
    assert res_top.index == 0
    assert res_top.segment.label == "TOP"

    # Hit right segment (1)
    res_right = hit_test(mid_r, 0.0, segs)
    assert res_right.hit_type == "segment"
    assert res_right.index == 1
    assert res_right.segment.label == "RIGHT"

    # Hit bottom segment (2)
    res_bottom = hit_test(0.0, mid_r, segs)
    assert res_bottom.hit_type == "segment"
    assert res_bottom.index == 2
    assert res_bottom.segment.label == "BOTTOM"

    # Hit left segment (3)
    res_left = hit_test(-mid_r, 0.0, segs)
    assert res_left.hit_type == "segment"
    assert res_left.index == 3
    assert res_left.segment.label == "LEFT"


def test_hit_test_secondary_ring():
    items = [{"label": "P1"}, {"label": "P2"}]
    primary = layout_segments(items, ring=1)

    sub_items = [{"label": "S1"}, {"label": "S2"}, {"label": "S3"}, {"label": "S4"}]
    secondary = layout_segments(sub_items, ring=2)

    # Secondary radius: e.g. 180 px
    res = hit_test(0.0, -180.0, primary, secondary)
    assert res.hit_type == "secondary"
    assert res.index == 0
    assert res.ring == 2


def test_hit_test_outside():
    items = [{"label": "P1"}]
    segs = layout_segments(items)

    res = hit_test(300.0, 300.0, segs)
    assert res.hit_type == "outside"


def test_navigate_direction():
    items = [
        {"label": "TOP"},
        {"label": "RIGHT"},
        {"label": "BOTTOM"},
        {"label": "LEFT"},
    ]
    segs = layout_segments(items)

    # Initial selection from unselected (-1)
    assert navigate_direction(-1, "up", segs) == 0
    assert navigate_direction(-1, "right", segs) == 1
    assert navigate_direction(-1, "down", segs) == 2
    assert navigate_direction(-1, "left", segs) == 3

    # Stepping clockwise with right
    assert navigate_direction(0, "right", segs) == 1
    assert navigate_direction(1, "right", segs) == 2
    assert navigate_direction(3, "right", segs) == 0

    # Stepping counter-clockwise with left
    assert navigate_direction(0, "left", segs) == 3
    assert navigate_direction(2, "left", segs) == 1
