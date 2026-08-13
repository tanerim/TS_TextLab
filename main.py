from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication, QMessageBox

from app.config import APP_NAME, ORGANIZATION_NAME
from app.logging_config import configure_logging
from app.main_window import MainWindow


def main() -> int:
    configure_logging()
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setOrganizationName(ORGANIZATION_NAME)

    try:
        window = MainWindow()
    except Exception as exc:
        QMessageBox.critical(None, "TS TextLab başlatılamadı", str(exc))
        return 1

    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
