"""Exercise the installed executable without accessing user preferences or the network."""

from __future__ import annotations

import csv
import json
import platform
import sys
import tempfile
import time
import traceback
from pathlib import Path

from PySide6.QtCore import QSettings, QTimer
from PySide6.QtWidgets import QApplication, QListWidget

from app.config import APP_VERSION
from app.export_service import write_tab_csv
from app.i18n import Translator
from app.main_window import MainWindow, SettingsDialog
from app.resource_manager import resolve_resource


def run_self_test(app: QApplication, report_path: str) -> int:
    report = {"version": APP_VERSION, "platform": platform.platform(), "utf8_mode": sys.flags.utf8_mode, "checks": [], "passed": False}
    window = None
    try:
        with tempfile.TemporaryDirectory(prefix="textlab-check-") as folder:
            QSettings.setDefaultFormat(QSettings.IniFormat)
            QSettings.setPath(QSettings.IniFormat, QSettings.UserScope, folder)
            window = MainWindow()
            window.show()
            app.processEvents()
            assert not window.windowIcon().isNull(), "Window icon is missing"
            assert not window.logo_pixmap.isNull(), "TS Corpus logo is missing"
            for name in ("app-icon.png", "app-icon.ico", "app-icon.icns", "chevron.svg", "check.svg"):
                assert resolve_resource("app", "theme", name).is_file(), f"Missing asset: {name}"
            report["checks"].append("window, icon, logo, packaged assets")

            def wait_for_task(kind: str) -> None:
                deadline = time.monotonic() + 120
                while window._busy:
                    app.processEvents()
                    if time.monotonic() > deadline:
                        raise TimeoutError(f"{kind} took more than 120 seconds")
                    time.sleep(0.01)
                app.processEvents()
                assert window.current_kind == kind, window.status_label.text()
                assert window.current_raw_result and window.current_raw_result.rows, f"Empty {kind} result"
                assert not window.analysis_progress.isVisible(), "Progress bar did not finish"
                assert window.analysis_summary_label.text(), "Missing timing summary"
                result = window.current_raw_result
                target = Path(folder) / f"{kind}.csv"
                write_tab_csv(target, result.headers, result.rows)
                with target.open(encoding="utf-8", newline="") as stream:
                    assert list(csv.reader(stream, delimiter="\t")) == [result.headers, *map(list, result.rows)]
                report["checks"].append(f"{kind}: {len(result.rows)} rows, CSV round trip")

            for index, kind in enumerate(("tokenize", "pos", "frequency", "ngrams", "dashboard")):
                window.action_tabs.setCurrentIndex(index)
                if kind == "tokenize":
                    window.tokenizer_mode_combo.setCurrentIndex(1)
                if kind != "dashboard":
                    window._start_task(kind)
                assert window._busy and window.analysis_progress.isVisible(), "Progress did not start"
                wait_for_task(kind)
                if kind == "tokenize":
                    assert window.tagged_note_label.isVisible(), "Tagged explanation is missing"

            window.action_tabs.setCurrentIndex(2)
            window._start_task("frequency")
            wait_for_task("frequency")
            window.filter_input.setText("bir")
            assert window.proxy_model.rowCount() > 0
            window.filter_input.clear()
            window.concordance_query_input.setText("bir")
            window._start_task("concordance")
            wait_for_task("concordance")
            window._restore_concordance_source()
            assert window.current_kind == "frequency"
            report["checks"].append("filter, concordance and back")

            for language in ("tr", "en"):
                window.trn = Translator(language)
                window._apply_translations()
                for width, height in ((980, 640), (1280, 800)):
                    window.resize(width, height)
                    app.processEvents()
                    assert window.width() == width and window.height() == height
                    assert not window.grab().isNull()
                settings = SettingsDialog(window.settings, window)
                settings.show()
                app.processEvents()
                assert not settings.grab().isNull()
                settings.reject()
                errors = []

                def inspect_help() -> None:
                    dialog = app.activeModalWidget()
                    try:
                        navigation = dialog.findChild(QListWidget, "HelpNavigation")
                        assert navigation and navigation.count() == 10
                        for row in range(10):
                            navigation.setCurrentRow(row)
                            app.processEvents()
                            assert not dialog.grab().isNull()
                    except Exception as exc:
                        errors.append(str(exc))
                    finally:
                        if dialog:
                            dialog.accept()

                QTimer.singleShot(50, inspect_help)
                window._show_guide()
                assert not errors, errors
            report["checks"].append("Turkish/English, two window sizes, settings and ten help pages")
            window._clear_all()
            assert not window.input_text.toPlainText() and window.result_model.rowCount() == 0
            window._start_task("tokenize")
            deadline = time.monotonic() + 10
            while window._busy:
                app.processEvents()
                assert time.monotonic() < deadline
                time.sleep(0.01)
            assert window.action_tabs.isEnabled() and not window.analysis_progress.isVisible()
            report["checks"].append("clear and error recovery")
            report["passed"] = True
    except Exception:
        report["error"] = traceback.format_exc()
    finally:
        if window:
            window.hide()
            window.thread_pool.waitForDone()
        target = Path(report_path).resolve()
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0 if report["passed"] else 1
