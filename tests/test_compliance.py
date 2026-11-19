"""Phase 0 compliance tests: branding cleanliness, accent migration, license policy, and zero-network guard."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def test_no_competitor_naming_in_wheel_onboarding_and_scripts():
    targets = [
        REPO_ROOT / "filetool" / "ui" / "styles.py",
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


def test_accent_preset_renamed_and_migrates_legacy_key(qapp, tmp_path):
    from PySide6.QtCore import QSettings
    from filetool.ui.styles import ACCENT_PRESETS, migrate_accent_setting, normalize_accent_key

    assert ACCENT_PRESETS["amber"]["label"] == "Amber"
    assert all("tangerine" not in preset["label"].lower() for preset in ACCENT_PRESETS.values())
    assert normalize_accent_key("tangerine") == "amber"
    assert normalize_accent_key("Tangerine") == "amber"
    assert normalize_accent_key("ocean") == "ocean"
    assert normalize_accent_key("unknown_value") == "amber"
    assert normalize_accent_key(None) == "amber"

    ini_path = tmp_path / "settings.ini"
    qs = QSettings(str(ini_path), QSettings.IniFormat)
    qs.setValue("accent_preset", "tangerine")
    migrated = migrate_accent_setting(qs)
    assert migrated == "amber"
    assert qs.value("accent_preset", "", type=str) == "amber"


def test_license_audit_flags_unapproved_agpl_and_unknown_packages():
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "audit_licenses", REPO_ROOT / "scripts" / "audit_licenses.py"
    )
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    assert mod.classify_license("MIT") == "permissive"
    assert mod.classify_license("BSD-3-Clause") == "permissive"
    assert mod.classify_license("LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only") == "weak-copyleft"
    assert mod.classify_license("Dual Licensed - GNU AFFERO GPL 3.0 or Artifex Commercial License") == "strong-copyleft"
    assert mod.classify_license("") == "unknown"

    sample = [
        {"name": "pypdf", "version": "6.21.1", "license": "BSD-3-Clause", "category": "permissive"},
        {"name": "pymupdf", "version": "1.28.2", "license": "AGPL-3.0", "category": "strong-copyleft"},
        {"name": "mysterypkg", "version": "0.1.0", "license": "UNKNOWN", "category": "unknown"},
    ]
    violations = mod.check_policy(sample, allowed_strong_copyleft=set())
    assert any("pymupdf" in v for v in violations)
    assert any("mysterypkg" in v for v in violations)
    assert mod.check_policy(sample[:2], allowed_strong_copyleft={"pymupdf"}) == []

    records = mod.collect_python_licenses()
    assert len(records) >= 10
    assert mod.check_policy(records) == []

    notices = REPO_ROOT / "THIRD_PARTY_NOTICES.md"
    assert notices.is_file()
    notices_text = notices.read_text(encoding="utf-8")
    assert "PySide6" in notices_text and "pymupdf" in notices_text and "Ghostscript" in notices_text


FORBIDDEN_NET_MODULES = {
    "urllib.request",
    "http",
    "http.client",
    "requests",
    "httpx",
    "aiohttp",
    "socket",
    "ftplib",
    "smtplib",
    "websockets",
    "xmlrpc",
}


def _find_forbidden_network_imports(source: str, filename: str = "<memory>") -> list[str]:
    import ast

    hits: list[str] = []
    tree = ast.parse(source, filename=filename)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                name = alias.name
                if name in FORBIDDEN_NET_MODULES or name.split(".")[0] in FORBIDDEN_NET_MODULES:
                    hits.append(f"{filename}:{node.lineno}:{name}")
        elif isinstance(node, ast.ImportFrom) and node.module:
            mod = node.module
            if mod in FORBIDDEN_NET_MODULES or mod.split(".")[0] in FORBIDDEN_NET_MODULES:
                hits.append(f"{filename}:{node.lineno}:{mod}")
    return hits


def test_no_outbound_network_imports_in_filetool():
    # Prove the detector catches real network imports while allowing urllib.parse
    assert _find_forbidden_network_imports("import urllib.parse\n") == []
    assert len(_find_forbidden_network_imports("import requests\n")) == 1
    assert len(_find_forbidden_network_imports("from urllib.request import urlopen\n")) == 1
    assert len(_find_forbidden_network_imports("import socket\n")) == 1

    hits: list[str] = []
    for path in sorted((REPO_ROOT / "filetool").rglob("*.py")):
        hits.extend(
            _find_forbidden_network_imports(
                path.read_text(encoding="utf-8"),
                filename=str(path.relative_to(REPO_ROOT)),
            )
        )
    assert hits == [], f"Unexpected outbound network imports found in filetool/: {hits}"


def test_privacy_docs_match_quartz_polling_and_manifest_covers_resources():
    for rel in ("PRIVACY.md", "filetool/core/legal.py"):
        text = (REPO_ROOT / rel).read_text(encoding="utf-8")
        assert "CGEventTap" not in text, f"{rel} still claims unused CGEventTap"
        assert "CGEventSource" in text, f"{rel} should document actual CGEventSource state queries"

    manifest = REPO_ROOT / "resources" / "ASSET_MANIFEST.md"
    assert manifest.is_file(), "Missing resources/ASSET_MANIFEST.md"
    manifest_text = manifest.read_text(encoding="utf-8")
    for asset in sorted((REPO_ROOT / "resources").iterdir()):
        if asset.name == "ASSET_MANIFEST.md" or asset.name.startswith("."):
            continue
        assert asset.name in manifest_text, f"{asset.name} missing from resources/ASSET_MANIFEST.md"

    checks_doc = REPO_ROOT / "docs" / "TRADEMARK_AND_PERMISSIONS_CHECK.md"
    assert checks_doc.is_file(), "Missing docs/TRADEMARK_AND_PERMISSIONS_CHECK.md"
