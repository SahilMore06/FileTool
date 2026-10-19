"""Radial geometry calculations, angle hit-testing, and segment layout."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, List, Optional, Tuple

HUB_RADIUS: float = 40.0
RING1_INNER_RADIUS: float = 48.64
RING1_OUTER_RADIUS: float = 119.52
RING2_INNER_RADIUS: float = 124.0
RING2_OUTER_RADIUS: float = 190.0

# Tangerine exact geometry constants
TANGERINE_INNER_RADIUS: float = 48.64
TANGERINE_OUTER_RADIUS: float = 119.52
TANGERINE_BACKDROP_RADIUS: float = 125.92
TANGERINE_CORNER_RADIUS: float = 20.16
TANGERINE_GAP: float = 4.0
TANGERINE_LABEL_INNER: float = 40.0
TANGERINE_WINDOW_SIZE: int = 340

# Gap angle between segments in degrees (visual separator)
SEGMENT_GAP_DEG: float = 2.0


def tangerine_angle(index: int, total: int) -> float:
    """Tangerine petal angle: 12 o'clock (PI/2) minus clockwise steps."""
    return (math.pi if total == 3 else math.pi / 2.0) - math.pi * 2.0 * index / total


def tangerine_be(radius: float, angle: float) -> Tuple[float, float]:
    """Cartesian (x, y) where angle 0 is +X and positive angles go counterclockwise."""
    return (math.cos(angle) * radius, -math.sin(angle) * radius)


def tangerine_petal_pos(index: int, total: int) -> Tuple[float, float]:
    """Centroid for label/icon placement matching Tangerine."""
    r = TANGERINE_LABEL_INNER + (TANGERINE_OUTER_RADIUS - TANGERINE_LABEL_INNER) * 0.56
    ang = tangerine_angle(index, total)
    return tangerine_be(r, ang)


def hit_test_tangerine(dx: float, dy: float, n_items: int) -> int:
    """Hit-test a point (dx, dy) against Tangerine petals. Returns index or -1."""
    n = math.hypot(dx, dy)
    if n_items <= 0 or n < TANGERINE_INNER_RADIUS or n > TANGERINE_OUTER_RADIUS + 4.0:
        return -1
    l = math.atan2(-dy, dx)
    s = math.pi * 2.0 / n_items
    f0 = tangerine_angle(0, n_items)
    r = ((f0 - l) % (math.pi * 2.0) + math.pi * 2.0) % (math.pi * 2.0)
    d = round(r / s) % n_items
    diff = math.atan2(math.sin(l - tangerine_angle(d, n_items)), math.cos(l - tangerine_angle(d, n_items)))
    if abs(diff) > s / 2.0 - math.asin(min(0.95, TANGERINE_GAP / 2.0 / max(n, 1.0))):
        return -1
    return d


@dataclass
class SegmentArc:
    """Represents a radial slice in the wheel."""
    index: int
    label: str
    icon_name: str
    start_angle: float       # degrees, 0 = 12 o'clock, increasing clockwise
    end_angle: float
    mid_angle: float
    inner_radius: float
    outer_radius: float
    ring: int = 1            # 1 = primary, 2 = secondary
    action_type: str = ""    # "convert", "tool", "action"
    action_data: Any = None  # target ext, tool func, or action callback
    sub_items: List[SegmentArc] = field(default_factory=list)

    @property
    def centroid(self) -> Tuple[float, float]:
        """(x, y) relative to wheel center for drawing label/icon."""
        r = (self.inner_radius + self.outer_radius) / 2.0
        # Convert clock angle (0 at top, clockwise) to Cartesian radians
        rad = math.radians(self.mid_angle - 90.0)
        return (r * math.cos(rad), r * math.sin(rad))


@dataclass
class HitResult:
    """Result of hit-testing a point relative to wheel center."""
    hit_type: str  # "hub", "segment", "secondary", "outside"
    index: int = -1
    ring: int = 1
    segment: Optional[SegmentArc] = None


def point_to_clock_degrees(dx: float, dy: float) -> float:
    """
    Convert (dx, dy) where dy points downwards (screen coordinates)
    into clock degrees [0, 360) where 0 is 12 o'clock and increases clockwise.
    """
    rad = math.atan2(dy, dx)
    deg = (math.degrees(rad) + 90.0) % 360.0
    return deg


def clock_degrees_to_cartesian(deg: float, radius: float) -> Tuple[float, float]:
    """Convert clock degree and radius to (dx, dy) screen coordinates."""
    rad = math.radians(deg - 90.0)
    return (radius * math.cos(rad), radius * math.sin(rad))


def layout_segments(
    items: List[dict],
    ring: int = 1,
    inner_radius: Optional[float] = None,
    outer_radius: Optional[float] = None,
) -> List[SegmentArc]:
    """
    Build SegmentArc list for items on a ring.
    Segment 0 is centered at 12 o'clock (0°).
    """
    if not items:
        return []

    r_in = inner_radius if inner_radius is not None else (RING1_INNER_RADIUS if ring == 1 else RING2_INNER_RADIUS)
    r_out = outer_radius if outer_radius is not None else (RING1_OUTER_RADIUS if ring == 1 else RING2_OUTER_RADIUS)

    n = len(items)
    span = 360.0 / n
    segments: List[SegmentArc] = []

    for i, item in enumerate(items):
        mid = (i * span) % 360.0
        start = (mid - span / 2.0) % 360.0
        end = (mid + span / 2.0) % 360.0

        sub_arcs: List[SegmentArc] = []
        if "sub_items" in item and item["sub_items"]:
            sub_arcs = layout_segments(item["sub_items"], ring=2)

        seg = SegmentArc(
            index=i,
            label=item.get("label", ""),
            icon_name=item.get("icon", ""),
            start_angle=start,
            end_angle=end,
            mid_angle=mid,
            inner_radius=r_in,
            outer_radius=r_out,
            ring=ring,
            action_type=item.get("action_type", ""),
            action_data=item.get("action_data", None),
            sub_items=sub_arcs,
        )
        segments.append(seg)

    return segments


def hit_test(
    dx: float,
    dy: float,
    primary_segments: List[SegmentArc],
    secondary_segments: Optional[List[SegmentArc]] = None,
) -> HitResult:
    """
    Hit-test a point (dx, dy) relative to wheel center.
    Uses Tangerine petal hit testing.
    """
    dist = math.hypot(dx, dy)

    # 1. Center hub hit
    if dist < RING1_INNER_RADIUS:
        return HitResult(hit_type="hub", index=-1, ring=0)

    # 2. Primary ring hit using Tangerine's formula
    if RING1_INNER_RADIUS <= dist <= RING1_OUTER_RADIUS + 6.0:
        if not primary_segments:
            return HitResult(hit_type="outside")
        n = len(primary_segments)
        idx = hit_test_tangerine(dx, dy, n)
        if idx >= 0 and idx < n:
            return HitResult(hit_type="segment", index=idx, ring=1, segment=primary_segments[idx])
        # If in the small gap between petals or near boundary, fallback to clock sector
        if dist <= RING1_OUTER_RADIUS + 2.0:
            clock_deg = point_to_clock_degrees(dx, dy)
            span = 360.0 / n
            shifted = (clock_deg + span / 2.0) % 360.0
            idx = int(shifted // span) % n
            return HitResult(hit_type="segment", index=idx, ring=1, segment=primary_segments[idx])

    # 3. Secondary ring hit (if open and active)
    if secondary_segments and RING2_INNER_RADIUS <= dist <= RING2_OUTER_RADIUS:
        n2 = len(secondary_segments)
        if n2 > 0:
            clock_deg = point_to_clock_degrees(dx, dy)
            span2 = 360.0 / n2
            shifted2 = (clock_deg + span2 / 2.0) % 360.0
            idx2 = int(shifted2 // span2) % n2
            seg2 = secondary_segments[idx2] if idx2 < len(secondary_segments) else None
            return HitResult(hit_type="secondary", index=idx2, ring=2, segment=seg2)

    return HitResult(hit_type="outside")


def navigate_direction(
    current_idx: int,
    direction: str,  # "left", "right", "up", "down"
    segments: List[SegmentArc],
) -> int:
    """
    Return the next segment index given a keyboard arrow direction.
    """
    if not segments:
        return -1
    n = len(segments)
    if current_idx < 0:
        # Initial selection based on direction
        targets = {"up": 0.0, "right": 90.0, "down": 180.0, "left": 270.0}
        target_angle = targets.get(direction.lower(), 0.0)
        best_idx = 0
        min_diff = 360.0
        for seg in segments:
            diff = abs((seg.mid_angle - target_angle + 180.0) % 360.0 - 180.0)
            if diff < min_diff:
                min_diff = diff
                best_idx = seg.index
        return best_idx

    if direction.lower() == "right":
        return (current_idx + 1) % n
    elif direction.lower() == "left":
        return (current_idx - 1) % n
    elif direction.lower() == "down":
        # Find segment whose angle is closest to 180° away or opposite
        opposite = (segments[current_idx].mid_angle + 180.0) % 360.0
        return _closest_segment_to_angle(opposite, segments)
    elif direction.lower() == "up":
        # Opposite or top
        return _closest_segment_to_angle(0.0, segments)
    return current_idx


def _closest_segment_to_angle(target_deg: float, segments: List[SegmentArc]) -> int:
    best_idx = 0
    min_diff = 360.0
    for seg in segments:
        diff = abs((seg.mid_angle - target_deg + 180.0) % 360.0 - 180.0)
        if diff < min_diff:
            min_diff = diff
            best_idx = seg.index
    return best_idx
