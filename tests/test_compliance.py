"""Phase 0 compliance tests: branding cleanliness, accent migration, license policy, and zero-network guard."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def test_no_competitor_naming_in_wheel_onboarding_and_scripts():
    targets = [
        REPO_ROOT / "filetool" / "ui" / "wheel" / "geometry.py",
        REPO_ROOT / "filetool" / "ui" / "wheel" / "wheel_painter.py",
        REPO_ROOT / "filetool" / "ui" / "onboarding.py",
        *sorted((REPO_ROOT / "scripts").glob("*.sh")),
    ]
    offenders = [
        str(path.relative_to(REPO_ROOT))
        for path in targets
        if path.exists() and "tangerine" in path.read_text(encoding="utf-8").lower()
    ]
    assert offenders == [], f"Found competitor naming in: {offenders}"


def test_radial_geometry_exports_neutral_symbols():
    from filetool.ui.wheel import geometry

    assert geometry.WHEEL_INNER_RADIUS == 48.64
    assert geometry.WHEEL_OUTER_RADIUS == 119.52
    assert geometry.WHEEL_BACKDROP_RADIUS == 125.92
    assert geometry.WHEEL_CORNER_RADIUS == 20.16
    assert geometry.WHEEL_GAP == 4.0
    assert geometry.WHEEL_LABEL_INNER == 40.0
    assert geometry.WHEEL_WINDOW_SIZE == 340
    assert geometry.hit_test_radial(0.0, -80.0, 6) == 0
    x, y = geometry.radial_petal_pos(0, 6)
    assert abs(x) < 1e-6 and y < 0
