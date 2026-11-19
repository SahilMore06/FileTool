"""Phase 0 compliance tests: branding cleanliness, accent migration, license policy, and zero-network guard."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def test_no_competitor_naming_in_wheel_onboarding_and_scripts():
    targets = [
        REPO_ROOT / "README.md",
        REPO_ROOT / "PRIVACY.md",
        REPO_ROOT / "TERMS.md",
        REPO_ROOT / "pyproject.toml",
        REPO_ROOT / "Dockerfile",
        REPO_ROOT / ".github" / "workflows" / "release.yml",
        *sorted((REPO_ROOT / "filetool").rglob("*.py")),
        *sorted((REPO_ROOT / "scripts").glob("*.py")),
        *sorted((REPO_ROOT / "scripts").glob("*.sh")),
        *[p for p in sorted((REPO_ROOT / "tests").rglob("*.py")) if p.name != "test_compliance.py"],
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
    assert mod.classify_license("GPL-2.0 OR see LICENSE for permitted use") == "strong-copyleft"
    assert mod.classify_license("Proprietary (submitted by author)") == "unknown"
    assert mod.classify_license("LGPL-2.1 AND GPL-3.0") == "strong-copyleft"
    assert mod.classify_license("MIT AND GPL-3.0") == "strong-copyleft"
    assert mod.classify_license("MIT OR GPL-3.0") == "permissive"
    assert mod.classify_license("") == "unknown"

    class _FakeMeta:
        def __init__(self, data, classifiers):
            self._data = data
            self._classifiers = classifiers

        def get(self, key, default=None):
            return self._data.get(key, default)

        def get_all(self, key, default=None):
            return self._classifiers if key == "Classifier" else default

    class _FakeDist:
        def __init__(self, data, classifiers):
            self.metadata = _FakeMeta(data, classifiers)
            self.version = "1.0.0"

    multiline_gpl = _FakeDist(
        {"Name": "sneaky-pkg", "License": "Copyright (c) 2026 Example Corp.\nSee full terms below."},
        ["License :: OSI Approved :: GNU General Public License v3 (GPLv3)"],
    )
    extracted = mod._extract_license_text(multiline_gpl)
    assert mod.classify_license(extracted) == "strong-copyleft"

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


ALLOWED_URLLIB_SUBMODULES = {"urllib.parse", "urllib.error"}

FORBIDDEN_NET_MODULES = {
    "urllib",
    "urllib.request",
    "urllib3",
    "http",
    "http.client",
    "requests",
    "httpx",
    "aiohttp",
    "socket",
    "ssl",
    "ftplib",
    "smtplib",
    "websockets",
    "xmlrpc",
    "pycurl",
    "httplib2",
    "PySide6.QtNetwork",
    "sentry_sdk",
    "posthog",
    "mixpanel",
    "amplitude",
    "analytics",
    "opentelemetry",
    "bugsnag",
    "rollbar",
    "datadog",
}


def _is_forbidden_module(name: str) -> bool:
    if name in ALLOWED_URLLIB_SUBMODULES or any(
        name.startswith(f"{allowed}.") for allowed in ALLOWED_URLLIB_SUBMODULES
    ):
        return False
    if name in FORBIDDEN_NET_MODULES:
        return True
    root = name.split(".")[0]
    if root in FORBIDDEN_NET_MODULES:
        return True
    return any(name.startswith(f"{forbidden}.") for forbidden in FORBIDDEN_NET_MODULES)


def _find_forbidden_network_imports(source: str, filename: str = "<memory>") -> list[str]:
    import ast

    hits: list[str] = []
    tree = ast.parse(source, filename=filename)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if _is_forbidden_module(alias.name):
                    hits.append(f"{filename}:{node.lineno}:{alias.name}")
        elif isinstance(node, ast.ImportFrom) and node.module:
            mod = node.module
            for alias in node.names:
                full = f"{mod}.{alias.name}"
                if _is_forbidden_module(full):
                    hits.append(f"{filename}:{node.lineno}:{full}")
            if not node.names and _is_forbidden_module(mod):
                hits.append(f"{filename}:{node.lineno}:{mod}")
    return hits


def test_no_outbound_network_imports_in_filetool():
    # Prove the detector catches direct, submodule, QtNetwork, and telemetry imports while allowing urllib.parse
    assert _find_forbidden_network_imports("import urllib.parse\n") == []
    assert _find_forbidden_network_imports("from urllib.parse import unquote\n") == []
    assert len(_find_forbidden_network_imports("import requests\n")) == 1
    assert len(_find_forbidden_network_imports("from urllib.request import urlopen\n")) == 1
    assert len(_find_forbidden_network_imports("from urllib import request\n")) == 1
    assert len(_find_forbidden_network_imports("import urllib\n")) == 1
    assert len(_find_forbidden_network_imports("from PySide6 import QtNetwork\n")) == 1
    assert len(_find_forbidden_network_imports("import PySide6.QtNetwork\n")) == 1
    assert len(_find_forbidden_network_imports("import urllib3\n")) == 1
    assert len(_find_forbidden_network_imports("import sentry_sdk\n")) == 1
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
    forbidden_claims = (
        "cgeventtap",
        "kcgeventflagschanged",
        "kcgannotatedsession",
        "quartz event tap",
        "passive quartz tap",
        "zero accessibility",
        "no accessibility",
    )
    checked_docs = (
        "PRIVACY.md",
        "TERMS.md",
        "SECURITY.md",
        "README.md",
        "docs/ARCHITECTURE.md",
        "docs/diagrams/filetool_architecture.html",
        "docs/diagrams/filetool_architecture.svg",
        "docs/diagrams/filetool_interaction_flow.html",
        "docs/diagrams/filetool_interaction_flow.svg",
        "filetool/core/legal.py",
        "filetool/ui/onboarding.py",
        ".github/workflows/release.yml",
    )
    for rel in checked_docs:
        text = (REPO_ROOT / rel).read_text(encoding="utf-8")
        lower = text.lower()
        for phrase in forbidden_claims:
            assert phrase not in lower, f"{rel} still contains inaccurate claim {phrase!r}"

    for rel in ("PRIVACY.md", "TERMS.md", "SECURITY.md", "README.md", "docs/ARCHITECTURE.md", "filetool/core/legal.py"):
        text = (REPO_ROOT / rel).read_text(encoding="utf-8")
        assert "CGEventSource" in text, f"{rel} should document actual CGEventSource state queries"

    for rel in ("README.md", "pyproject.toml", "Dockerfile", ".github/workflows/release.yml"):
        text = (REPO_ROOT / rel).read_text(encoding="utf-8")
        assert "www.fluxora.live" not in text, f"{rel} still uses non-canonical www.fluxora.live"
        assert "https://fluxora.live" in text, f"{rel} should link to canonical https://fluxora.live"

    manifest = REPO_ROOT / "resources" / "ASSET_MANIFEST.md"
    assert manifest.is_file(), "Missing resources/ASSET_MANIFEST.md"
    manifest_text = manifest.read_text(encoding="utf-8")
    for asset in sorted((REPO_ROOT / "resources").iterdir()):
        if asset.name == "ASSET_MANIFEST.md" or asset.name.startswith("."):
            continue
        assert asset.name in manifest_text, f"{asset.name} missing from resources/ASSET_MANIFEST.md"

    checks_doc = REPO_ROOT / "docs" / "TRADEMARK_AND_PERMISSIONS_CHECK.md"
    assert checks_doc.is_file(), "Missing docs/TRADEMARK_AND_PERMISSIONS_CHECK.md"
