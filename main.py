from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication, QMessageBox
from PySide6.QtGui import QIcon

from app.config import APP_NAME, ORGANIZATION_NAME
from app.logging_config import configure_logging
from app.main_window import MainWindow
from app.resource_manager import resolve_resource


def main() -> int:
    configure_logging()
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setOrganizationName(ORGANIZATION_NAME)
    app.setDesktopFileName("com.tscorpus.textlab")
    app.setWindowIcon(QIcon(str(resolve_resource("app", "theme", "app-icon.png"))))

    if "--self-test" in sys.argv:
        from app.build_check import run_self_test
        report_index = sys.argv.index("--self-test") + 1
        report_path = sys.argv[report_index] if report_index < len(sys.argv) else "self-test.json"
        return run_self_test(app, report_path)

    try:
        window = MainWindow()
    except Exception as exc:
        QMessageBox.critical(None, "TS TextLab başlatılamadı", str(exc))
        return 1

    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
