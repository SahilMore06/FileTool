"""Tests for UI components, JobRunner, and main window integration."""

from __future__ import annotations

import sys
from pathlib import Path
import pytest
from PySide6.QtWidgets import QApplication

from filetool.core.runner import ConversionJob, JobRunner, JobStatus
from filetool.ui.main_window import MainWindow


@pytest.fixture(scope="session")
def qapp():
    """Ensure QApplication instance exists for widget tests."""
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    return app


def test_job_runner_workflow(qapp, samples_dir: Path, tmp_path: Path):
    """Test background runner executes a conversion job and emits signals."""
    runner = JobRunner(max_threads=2)
    src_file = samples_dir / "sample.png"

    job = ConversionJob(
        src_path=src_file,
        dest_ext="jpg",
        target_dir=tmp_path,
        options={"quality": 85},
    )

    runner.add_job(job)
    assert job.id in runner.jobs
    assert job.status == JobStatus.PENDING

    # Start job and wait for thread execution
    runner.start_job(job.id)
    runner.thread_pool.waitForDone(5000)

    assert job.status == JobStatus.SUCCESS
    assert job.dest_path is not None
    assert job.dest_path.exists()
    assert job.progress == 100


def test_job_runner_cancellation(qapp, samples_dir: Path, tmp_path: Path):
    """Test cancelling a pending job."""
    runner = JobRunner(max_threads=2)
    src_file = samples_dir / "sample.mp4"

    job = ConversionJob(
        src_path=src_file,
        dest_ext="mov",
        target_dir=tmp_path,
    )

    runner.add_job(job)
    runner.cancel_job(job.id)
    assert job.status == JobStatus.CANCELLED


def test_main_window_add_files(qapp, samples_dir: Path):
    """Test adding files to MainWindow populates queue and switches view."""
    window = MainWindow()
    src1 = samples_dir / "sample.png"
    src2 = samples_dir / "sample.wav"

    window._on_files_dropped([src1, src2])
    assert len(window.runner.jobs) == 2
    assert window.stack.currentIndex() == 1  # Switched from dropzone to joblist

    # Test bulk combo
    window.bulk_combo.setCurrentIndex(1)
    window._apply_bulk_format(1)

    window.close()


def test_main_window_clean_initial_state(qapp):
    """Initial window starts empty on Convert tab with collapsed Options."""
    window = MainWindow()
    assert len(window.runner.jobs) == 0
    assert window.pages.currentIndex() == 0
    assert window.stack.currentIndex() == 0
    assert window.history_panel.table.rowCount() == 0
    assert window.options_panel.parent() is not None
    assert window.options_panel.isHidden() is True
    assert window.convert_btn.isEnabled() is False
    assert window.bulk_combo.isEnabled() is False
    window.close()


def test_tab_navigation_and_options_drawer(qapp):
    """Top tabs switch pages cleanly and Options toggles the settings drawer."""
    window = MainWindow()
    window._navigate("history")
    assert window.pages.currentIndex() == 1

    window._navigate("settings")
    assert window.pages.currentIndex() == 2

    window._navigate("queue")
    assert window.pages.currentIndex() == 0

    window.options_btn.setChecked(True)
    assert window.options_panel.isHidden() is False
    window.options_btn.setChecked(False)
    assert window.options_panel.isHidden() is True
    window.close()


def test_theme_and_accent_switching(qapp):
    window = MainWindow()
    orig_dark = window.dark_mode
    orig_accent = window.accent_key
    try:
        window._on_theme_toggled(True)
        assert window.dark_mode is True

        window._on_accent_changed("ocean")
        assert window.accent_key == "ocean"

        window._on_theme_toggled(False)
        assert window.dark_mode is False
    finally:
        window._on_theme_toggled(orig_dark)
        window._on_accent_changed(orig_accent)
        window.close()


def test_queue_convert_updates_history_and_clear(qapp, samples_dir: Path, tmp_path: Path):
    """Running a queued image conversion writes output, logs history, and resets when cleared."""
    import shutil

    local_png = tmp_path / "photo.png"
    shutil.copy(samples_dir / "sample.png", local_png)

    window = MainWindow()
    window.custom_output_dir = tmp_path
    window._on_files_dropped([local_png])
    assert window.stack.currentIndex() == 1

    jpg_idx = window.bulk_combo.findData("jpg")
    assert jpg_idx > 0
    window.bulk_combo.setCurrentIndex(jpg_idx)
    window._apply_bulk_format(jpg_idx)

    window._start_all_jobs()
    assert window.runner.thread_pool.waitForDone(5000)
    qapp.processEvents()

    assert (tmp_path / "photo.jpg").exists()
    assert window.history_panel.table.rowCount() >= 1

    window._clear_completed()
    assert len(window.runner.jobs) == 0
    assert window.stack.currentIndex() == 0
    window.close()


def test_settings_validation_flags_duplicate_triggers_and_missing_folder(qapp, tmp_path: Path):
    """SettingsPage highlights duplicate triggers without saving conflicts and flags missing folders."""
    from filetool.ui.settings_page import SettingsPage

    page = SettingsPage()
    orig_convert = page.combo_convert.currentText()
    orig_tools = page.combo_tools.currentText()
    orig_saved_tools = page.qsettings.value("trigger_tools", orig_tools, type=str)
    orig_dir_enabled = page.sw_custom_dir.isChecked()
    orig_dir_text = page.dir_input.text()
    try:
        page.combo_tools.setCurrentText(orig_convert)
        errors = page.validate()
        assert any("different modifier" in e for e in errors)
        assert page.trigger_warning.isHidden() is False
        assert page.combo_tools.property("invalid") is True
        assert page.qsettings.value("trigger_tools", orig_tools, type=str) == orig_saved_tools

        page.combo_tools.setCurrentText(orig_tools if orig_tools != orig_convert else "Command")
        page.dir_input.setText(str(tmp_path / "does_not_exist"))
        page.sw_custom_dir.setChecked(True)
        errors = page.validate()
        assert any("Folder not found" in e for e in errors)
        assert page.dir_warning.isHidden() is False
        assert page.dir_input.property("invalid") is True

        page.dir_input.setText(str(tmp_path))
        assert page.validate() == []
        assert page.trigger_warning.isHidden() is True
        assert page.dir_warning.isHidden() is True
        assert page.dir_input.property("invalid") is False
    finally:
        page.combo_convert.setCurrentText(orig_convert)
        page.combo_tools.setCurrentText(orig_tools)
        page.dir_input.setText(orig_dir_text)
        page.sw_custom_dir.setChecked(orig_dir_enabled)
        page._persist_and_emit()
        page.close()


def test_theme_tokens_meet_wcag_aa_contrast():
    """Text, status, disabled, and wheel petal pairs meet WCAG AA (4.5:1) across presets."""
    from PySide6.QtGui import QColor

    from filetool.ui.styles import ACCENT_PRESETS, contrast_ratio, get_tokens
    from filetool.ui.wheel.wheel_painter import _wcag_contrast_ink

    for dark in (False, True):
        for preset in ACCENT_PRESETS:
            t = get_tokens(dark, accent_key=preset)
            assert contrast_ratio(t["text_primary"], t["bg_main"]) >= 4.5
            assert contrast_ratio(t["text_primary"], t["bg_surface"]) >= 4.5
            assert contrast_ratio(t["text_secondary"], t["bg_main"]) >= 4.5
            assert contrast_ratio(t["text_secondary"], t["bg_surface"]) >= 4.5
            assert contrast_ratio(t["text_secondary"], t["bg_surface2"]) >= 4.5
            assert contrast_ratio(t["text_muted"], t["bg_surface2"]) >= 4.5
            assert contrast_ratio(t["accent_text"], t["accent_subtle"]) >= 4.5
            assert contrast_ratio(t["accent_text"], t["bg_surface"]) >= 4.5
            assert contrast_ratio(t["accent_fg"], t["accent"]) >= 4.5
            assert contrast_ratio(t["accent_fg"], t["accent_hover"]) >= 4.5
            assert contrast_ratio(t["accent_fg"], t["accent_pressed"]) >= 4.5
            assert contrast_ratio(t["success"], t["bg_surface"]) >= 4.5
            assert contrast_ratio(t["success"], t["success_subtle"]) >= 4.5
            assert contrast_ratio(t["error"], t["bg_surface"]) >= 4.5
            assert contrast_ratio(t["error"], t["error_subtle"]) >= 4.5
            assert contrast_ratio(t["warning"], t["warning_subtle"]) >= 4.5

            ink = _wcag_contrast_ink(QColor(t["accent"]))
            assert contrast_ratio(ink.name(), t["accent"]) >= 4.5


def test_brand_emblem_and_logo_animations(qapp):
    """Retina brand emblem renders cleanly and LogoWidget toggles active spin/done states."""
    from filetool.app import TrayAnimator, create_tray_icon
    from filetool.ui.components import LogoWidget, create_brand_icon, create_brand_pixmap
    from PySide6.QtWidgets import QSystemTrayIcon

    pix = create_brand_pixmap(size=20, accent_color="#F28A32", dpr=2.0, progress=68)
    assert not pix.isNull()
    assert pix.width() == 40
    assert pix.devicePixelRatio() == 2.0

    icon = create_brand_icon("#2F6FED")
    assert not icon.isNull()
    assert not create_tray_icon().isNull()

    logo = LogoWidget(size=28)
    logo.spin_once(60.0)
    logo.set_active_progress(True, 50)
    assert logo._progress == 50
    logo.trigger_done_flash()
    assert logo._progress is None
    assert logo._spinning is False

    tray = QSystemTrayIcon(create_tray_icon())
    anim = TrayAnimator(tray)
    anim.set_wheel_open(True)
    anim.set_queue_state(2, 45, False)
    assert anim._converting is True
    assert anim._progress == 45
    anim.set_queue_state(0, 100, True)
    assert anim._converting is False
    assert anim._progress is None


def test_tray_popover_state_signals_and_drop(qapp, tmp_path: Path):
    """TrayPopover updates state cards cleanly, toggles wheel, and forwards dropped files."""
    from PySide6.QtCore import QMimeData, QPointF, Qt, QUrl
    from PySide6.QtGui import QDropEvent

    from filetool.ui.tray_popover import TrayPopover

    sample = tmp_path / "sample.png"
    sample.write_bytes(b"png")

    pop = TrayPopover(dark_mode=True, accent_key="amber")
    pop.update_state(
        wheel_enabled=True,
        key_mappings={"option": "convert", "command": "tools", "control": "actions"},
        active_jobs=1,
        progress_pct=75,
        tools_summary="10 of 10 local tools ready",
    )
    assert "Converting 1 file" in pop.subtitle_lbl.text()
    assert pop.progress_bar.isHidden() is False
    assert pop._trigger_chips[0].text() == "⌥ Convert"

    toggled_states = []
    pop.wheel_toggled.connect(toggled_states.append)
    pop.wheel_pill.click()
    assert toggled_states == [False]
    assert pop.wheel_pill.text() == "Paused"

    dropped_batches = []
    pop.files_dropped.connect(dropped_batches.append)
    mime = QMimeData()
    mime.setUrls([QUrl.fromLocalFile(str(sample))])
    ev = QDropEvent(QPointF(10, 10), Qt.CopyAction, mime, Qt.LeftButton, Qt.NoModifier)
    pop.dropEvent(ev)
    assert dropped_batches == [[sample.resolve()]]
    pop.close()


def test_haptic_patterns_and_sequence(qapp, monkeypatch):
    """macOS haptic helper maps generic, alignment, and level_change patterns cleanly."""
    import types
    from filetool.platform import mac_actions

    recorded = []

    class DummyPerformer:
        def performFeedbackPattern_performanceTime_(self, pattern, when):
            recorded.append((pattern, when))

    class DummyFeedbackManager:
        @classmethod
        def defaultPerformer(cls):
            return DummyPerformer()

    fake_appkit = types.SimpleNamespace(
        NSHapticFeedbackManager=DummyFeedbackManager,
        NSHapticFeedbackPatternGeneric=0,
        NSHapticFeedbackPatternAlignment=1,
        NSHapticFeedbackPatternLevelChange=2,
        NSHapticFeedbackPerformanceTimeDefault=0,
        NSHapticFeedbackPerformanceTimeNow=1,
        NSHapticFeedbackPerformanceTimeDrawCompleted=2,
    )
    monkeypatch.setitem(sys.modules, "AppKit", fake_appkit)

    assert mac_actions.trigger_haptic_tick("generic") is True
    assert mac_actions.trigger_haptic_tick("alignment") is True
    assert mac_actions.trigger_haptic_tick("level_change") is True
    assert [(p, w) for p, w in recorded] == [(0, 1), (1, 1), (2, 1)]

    timers = mac_actions.trigger_haptic_sequence([(0, "alignment"), (5, "level_change")])
    assert len(timers) == 1
    for t in timers:
        t.stop()


def test_legal_docs_and_first_boot_check(tmp_path: Path):
    """First-boot guard stays active until current legal version and onboarding are accepted."""
    from PySide6.QtCore import QSettings

    from filetool.app import needs_first_boot_onboarding
    from filetool.core.legal import LEGAL_VERSION, render_legal_html
    from filetool.ui.styles import get_tokens

    qs = QSettings(str(tmp_path / "first_boot.ini"), QSettings.IniFormat)
    assert needs_first_boot_onboarding(qs) is True

    qs.setValue("onboarding_completed", True)
    qs.setValue("legal_accepted", True)
    qs.setValue("legal_accepted_version", "0.0")
    assert needs_first_boot_onboarding(qs) is True

    qs.setValue("legal_accepted_version", LEGAL_VERSION)
    assert needs_first_boot_onboarding(qs) is False

    tokens = get_tokens(False, "amber")
    privacy_html = render_legal_html("privacy", tokens)
    terms_html = render_legal_html("terms", tokens)
    assert "zero network requests" in privacy_html.lower()
    assert "mit license" in terms_html.lower()
    assert "as is" in terms_html.lower()


def test_onboarding_starter_animation_haptic_sandbox_and_consent(qapp, tmp_path: Path, monkeypatch):
    """Onboarding animates starter emblem, fires haptics in sandbox, requires consent, and saves settings."""
    from PySide6.QtCore import QPointF, QSettings, Qt
    from PySide6.QtGui import QMouseEvent

    from filetool.core.legal import LEGAL_VERSION
    from filetool.platform import mac_actions
    from filetool.ui import onboarding as ob_mod

    haptic_events = []

    def _capture_haptic(pattern="generic", when="now"):
        haptic_events.append(pattern)
        return True

    monkeypatch.setattr(ob_mod, "trigger_haptic_tick", _capture_haptic)
    monkeypatch.setattr(mac_actions, "trigger_haptic_tick", _capture_haptic)

    qs = QSettings(str(tmp_path / "onboarding.ini"), QSettings.IniFormat)
    win = ob_mod.OnboardingWindow(dark_mode=False, accent_key="amber", first_boot=True, qsettings=qs)

    # Step 0: starter install choreography + real QPainter render check
    win.hero_canvas.play_install_sequence(emit_haptics=True)
    win.hero_canvas._on_install_step(0.5)
    assert not win.hero_canvas.grab().isNull()
    win.hero_canvas._on_install_step(1.0)
    win.hero_canvas._on_install_done()
    assert not win.hero_canvas.grab().isNull()
    assert win.hero_canvas._install_t == 1.0
    assert all(pill.property("ready") is True for pill in win._cap_labels)
    assert "alignment" in haptic_events
    assert "level_change" in haptic_events

    # Step 1: haptic wheel sandbox boundary detent + switch + theme swap
    win.go_to_step(ob_mod.OnboardingWindow.STEP_SANDBOX)
    win._pick_sandbox_wheel("tools")
    assert win.wheel_sandbox._wheel_type == "tools"

    prev_haptics = len(haptic_events)
    cx, cy = win.wheel_sandbox.width() / 2.0, win.wheel_sandbox.height() / 2.0 - 80.0
    win.wheel_sandbox._update_hover(QPointF(cx, cy))
    assert win.wheel_sandbox._hovered_idx == 0
    assert len(haptic_events) > prev_haptics

    click_ev = QMouseEvent(
        QMouseEvent.Type.MouseButtonPress,
        QPointF(cx, cy),
        QPointF(cx, cy),
        Qt.LeftButton,
        Qt.LeftButton,
        Qt.NoModifier,
    )
    win.wheel_sandbox.mousePressEvent(click_ev)
    assert not win.wheel_sandbox.grab().isNull()
    assert "Tools" in win.sandbox_status.text()
    win._on_accent_picked("ocean")
    assert win._accent_key == "ocean"

    # Step 2: legal reader + validation guard + completion
    win.go_to_step(ob_mod.OnboardingWindow.STEP_LEGAL)
    assert "Privacy Policy" in win.legal_browser.toPlainText()
    win.select_legal_doc("terms")
    assert "MIT" in win.legal_browser.toPlainText()

    # Clicking Accept before checking box refuses and shakes
    win._on_primary()
    assert not win.consent_checkbox.grab().isNull()
    assert win.consent_warning.isHidden() is False
    assert qs.value("legal_accepted", False, type=bool) is False

    # Accepting saves state and emits payload
    completed_payloads = []
    win.onboarding_completed.connect(completed_payloads.append)
    win.consent_checkbox.setChecked(True)
    win.complete_onboarding(animate_exit=False)

    assert len(completed_payloads) == 1
    assert qs.value("onboarding_completed", False, type=bool) is True
    assert qs.value("legal_accepted", False, type=bool) is True
    assert qs.value("legal_accepted_version", "", type=str) == LEGAL_VERSION
    assert qs.value("accent_preset", "", type=str) == "ocean"
    win.close()


def test_settings_legal_actions_and_main_window_replay(qapp, tmp_path: Path):
    """MainWindow Settings replay buttons open the matching onboarding stage cleanly."""
    from PySide6.QtCore import QSettings

    window = MainWindow()
    iso_qs = QSettings(str(tmp_path / "replay.ini"), QSettings.IniFormat)
    try:
        assert window.settings_page.legal_status_badge.text()
        ob = window.open_onboarding(first_boot=False, initial_step=2, initial_legal_doc="terms", qsettings=iso_qs)
        assert ob._current_step == 2
        assert ob._legal_doc == "terms"
        ob.close()
    finally:
        window.close()
