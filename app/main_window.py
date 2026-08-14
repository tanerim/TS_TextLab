"""PySide6 main window."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Literal

from PySide6.QtCore import (
    QAbstractTableModel,
    QModelIndex,
    QObject,
    QRegularExpression,
    QRunnable,
    QRectF,
    QSettings,
    QSortFilterProxyModel,
    Qt,
    QThreadPool,
    QTimer,
    Signal,
    Slot,
)
from PySide6.QtGui import QColor, QGuiApplication, QKeySequence, QPainter, QPen, QShortcut, QTextCursor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QPlainTextEdit,
    QSplitter,
    QStackedWidget,
    QStyle,
    QStyledItemDelegate,
    QTableView,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from app.config import APP_NAME, APP_VERSION, DEFAULT_SAMPLE_TEXT, MAX_INPUT_CHARS
from app.errors import TextLabError
from app.i18n import Translator
from app.postagger_service import PosTaggerService
from app.theme.theme_manager import ThemeName, ThemePalette, apply_theme, palette_for
from app.tokenizer_service import FrequencyCaseMode, TokenizerMode, TokenizerService
from app.version_service import VersionCheckResult, check_for_update

logger = logging.getLogger(__name__)
TaskKind = Literal["tokenize", "pos", "frequency"]


@dataclass(frozen=True)
class TaskResult:
    kind: TaskKind
    headers: list[str]
    rows: list[tuple[str, ...]]
    copy_text: str
    tokenizer_mode: TokenizerMode | None = None
    frequency_case_mode: FrequencyCaseMode | None = None


class WorkerSignals(QObject):
    finished = Signal(object)
    failed = Signal(str)


class VersionSignals(QObject):
    finished = Signal(object)


class VersionWorker(QRunnable):
    def __init__(self) -> None:
        super().__init__()
        self.setAutoDelete(False)
        self.signals = VersionSignals()

    @Slot()
    def run(self) -> None:
        result = check_for_update()
        try:
            self.signals.finished.emit(result)
        except RuntimeError:
            logger.debug("Version check finished after UI shutdown")


class NlpWorker(QRunnable):
    def __init__(
        self,
        kind: TaskKind,
        text: str,
        tokenizer_mode: TokenizerMode,
        frequency_case_mode: FrequencyCaseMode,
        tokenizer_service: TokenizerService,
        postagger_service: PosTaggerService,
    ) -> None:
        super().__init__()
        self.setAutoDelete(False)
        self.kind = kind
        self.text = text
        self.tokenizer_mode = tokenizer_mode
        self.frequency_case_mode = frequency_case_mode
        self.tokenizer_service = tokenizer_service
        self.postagger_service = postagger_service
        self.signals = WorkerSignals()

    @Slot()
    def run(self) -> None:
        try:
            if len(self.text) > MAX_INPUT_CHARS:
                raise TextLabError(
                    f"Metin çok uzun. İlk sürümde en fazla {MAX_INPUT_CHARS:,} karakter işlenebilir."
                )
            if self.kind == "tokenize":
                tokenizer_result = self.tokenizer_service.tokenize(self.text, self.tokenizer_mode)
                result = TaskResult(
                    kind=self.kind,
                    headers=tokenizer_result.headers,
                    rows=tokenizer_result.rows,
                    copy_text=tokenizer_result.copy_text,
                    tokenizer_mode=self.tokenizer_mode,
                )
            elif self.kind == "frequency":
                frequency_result = self.tokenizer_service.frequency(self.text, self.frequency_case_mode)
                result = TaskResult(
                    kind=self.kind,
                    headers=frequency_result.headers,
                    rows=frequency_result.rows,
                    copy_text=frequency_result.copy_text,
                    frequency_case_mode=self.frequency_case_mode,
                )
            else:
                tagged_tokens = self.tokenizer_service.tagged_tokens_for_pos(self.text)
                rows = [(token, tag) for token, tag in self.postagger_service.tag_tagged_tokens(tagged_tokens)]
                result = TaskResult(
                    kind=self.kind,
                    headers=["Token", "POS"],
                    rows=rows,
                    copy_text="\n".join(f"{token}\t{tag}" for token, tag in rows),
                )
            self.signals.finished.emit(result)
        except TextLabError as exc:
            logger.warning("NLP task failed: %s", exc)
            self.signals.failed.emit(str(exc))
        except Exception as exc:  # pragma: no cover - GUI boundary guard
            logger.exception("Unexpected NLP task failure")
            self.signals.failed.emit(f"Beklenmeyen bir hata oluştu: {exc}")


class ResultTableModel(QAbstractTableModel):
    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.kind: TaskKind | None = None
        self.headers: list[str] = []
        self.rows: list[tuple[str, ...]] = []

    def set_result(self, result: TaskResult | None) -> None:
        self.beginResetModel()
        if result is None:
            self.kind = None
            self.headers = []
            self.rows = []
        else:
            self.kind = result.kind
            self.headers = result.headers
            self.rows = result.rows
        self.endResetModel()

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self.rows)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self.headers) + 1

    def data(self, index: QModelIndex, role: int = Qt.DisplayRole) -> object:
        if not index.isValid():
            return None
        row = index.row()
        column = index.column()
        if row >= len(self.rows):
            return None

        if role == Qt.DisplayRole:
            if column == 0:
                return str(row + 1)
            value_index = column - 1
            return self.rows[row][value_index] if value_index < len(self.rows[row]) else ""

        if role == Qt.TextAlignmentRole:
            if column == 0 or (self.kind == "frequency" and column == 2):
                return int(Qt.AlignRight | Qt.AlignVCenter)
            return int(Qt.AlignLeft | Qt.AlignVCenter)

        if role == Qt.UserRole:
            if column == 0:
                return row + 1
            value_index = column - 1
            value = self.rows[row][value_index] if value_index < len(self.rows[row]) else ""
            if self.kind == "frequency" and column == 2:
                try:
                    return int(value)
                except ValueError:
                    return 0
            return value.casefold()

        return None

    def headerData(self, section: int, orientation: Qt.Orientation, role: int = Qt.DisplayRole) -> object:
        if role != Qt.DisplayRole or orientation != Qt.Horizontal:
            return None
        if section == 0:
            return "#"
        return self.headers[section - 1] if section - 1 < len(self.headers) else ""

    def copy_rows(self, source_rows: list[int] | None = None) -> str:
        rows = self.rows if source_rows is None else [self.rows[row] for row in source_rows if row < len(self.rows)]
        return "\n".join("\t".join(row) for row in rows)


class ResultProxyModel(QSortFilterProxyModel):
    def filterAcceptsRow(self, source_row: int, source_parent: QModelIndex) -> bool:
        pattern = self.filterRegularExpression().pattern()
        if not pattern:
            return True
        model = self.sourceModel()
        if model is None:
            return True
        text = pattern.casefold()
        for column in range(1, model.columnCount()):
            value = model.index(source_row, column, source_parent).data(Qt.DisplayRole)
            if text in str(value).casefold():
                return True
        return False

    def lessThan(self, left: QModelIndex, right: QModelIndex) -> bool:
        left_value = left.data(Qt.UserRole)
        right_value = right.data(Qt.UserRole)
        if isinstance(left_value, int) and isinstance(right_value, int):
            return left_value < right_value
        return str(left_value) < str(right_value)


class PosBadgeDelegate(QStyledItemDelegate):
    LIGHT_COLORS = {
        "NOUN": ("#E5F1FF", "#1F4F82"),
        "PROPN": ("#E9E7FF", "#4B3D93"),
        "VERB": ("#E3F7EC", "#1F6A43"),
        "AUX": ("#E8F5F2", "#1E665E"),
        "ADJ": ("#FFF1D8", "#7A4B00"),
        "ADV": ("#FCE5EF", "#823454"),
        "DET": ("#E6F6FA", "#1F6070"),
        "PRON": ("#EFE7FA", "#5C3B82"),
        "ADP": ("#F1F4F8", "#44546A"),
        "CCONJ": ("#F0EAF2", "#684064"),
        "SCONJ": ("#F0EAF2", "#684064"),
        "NUM": ("#F8E7DE", "#7A3E24"),
        "PUNCT": ("#ECEFF3", "#4D5968"),
    }
    DARK_COLORS = {
        "NOUN": ("#243D5D", "#BBD8FF"),
        "PROPN": ("#37325F", "#D9D2FF"),
        "VERB": ("#244937", "#BDEBCF"),
        "AUX": ("#244842", "#BEE9E1"),
        "ADJ": ("#52401F", "#F4D194"),
        "ADV": ("#523044", "#F5BDD2"),
        "DET": ("#234A54", "#BEEAF2"),
        "PRON": ("#3E3153", "#DDC8F5"),
        "ADP": ("#313A47", "#CDD6E2"),
        "CCONJ": ("#473244", "#E7C6E2"),
        "SCONJ": ("#473244", "#E7C6E2"),
        "NUM": ("#54382B", "#F1C5AD"),
        "PUNCT": ("#343A44", "#D3DAE3"),
    }

    def __init__(self, palette: ThemePalette, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.palette = palette

    def paint(self, painter: QPainter, option, index: QModelIndex) -> None:  # type: ignore[override]
        if index.column() != 2:
            super().paint(painter, option, index)
            return

        painter.save()
        if option.state & QStyle.State_Selected:
            painter.fillRect(option.rect, option.palette.highlight())
        text = str(index.data(Qt.DisplayRole) or "")
        rect = option.rect.adjusted(10, 7, -10, -7)
        width = min(rect.width(), option.fontMetrics.horizontalAdvance(text) + 20)
        badge = QRectF(rect.left(), rect.top(), width, rect.height())
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(Qt.NoPen)
        bg, fg = self._colors_for(text)
        painter.setBrush(QColor(bg))
        painter.drawRoundedRect(badge, 6, 6)
        painter.setPen(QPen(QColor(fg)))
        painter.drawText(badge, Qt.AlignCenter, text)
        painter.restore()

    def _colors_for(self, text: str) -> tuple[str, str]:
        key = text.strip().upper().split(":", 1)[0].split("-", 1)[0]
        colors = self.DARK_COLORS if self.palette.name == "dark" else self.LIGHT_COLORS
        return colors.get(key, (self.palette.pos_badge_bg, self.palette.pos_badge_text))


class FrequencyBarDelegate(QStyledItemDelegate):
    def __init__(self, palette: ThemePalette, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.palette = palette

    def paint(self, painter: QPainter, option, index: QModelIndex) -> None:  # type: ignore[override]
        if index.column() != 2:
            super().paint(painter, option, index)
            return

        model = index.model()
        max_count = 1
        for row in range(model.rowCount()):
            value = model.index(row, index.column()).data(Qt.UserRole)
            if isinstance(value, int):
                max_count = max(max_count, value)

        painter.save()
        if option.state & QStyle.State_Selected:
            painter.fillRect(option.rect, option.palette.highlight())
        count = int(index.data(Qt.UserRole) or 0)
        track = option.rect.adjusted(10, 12, -54, -12)
        if track.width() > 24:
            fill = QRectF(track)
            fill.setWidth(max(4, track.width() * count / max_count))
            painter.setRenderHint(QPainter.Antialiasing)
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(self.palette.bar_fill))
            painter.drawRoundedRect(fill, 4, 4)
        painter.setPen(QPen(QColor(self.palette.text)))
        painter.drawText(option.rect.adjusted(0, 0, -12, 0), Qt.AlignRight | Qt.AlignVCenter, str(count))
        painter.restore()


class EmptyState(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("EmptyState")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(8)
        layout.addStretch(1)
        self.title = QLabel("No results yet")
        self.title.setObjectName("EmptyTitle")
        self.title.setAlignment(Qt.AlignCenter)
        self.body = QLabel("Enter Turkish text and choose Tokenize, POS Tag or Frequency.")
        self.body.setObjectName("HintLabel")
        self.body.setAlignment(Qt.AlignCenter)
        self.body.setWordWrap(True)
        layout.addWidget(self.title)
        layout.addWidget(self.body)
        layout.addStretch(1)

    def apply_translations(self, trn: Translator) -> None:
        self.title.setText(trn.text("no_results_title"))
        self.body.setText(trn.text("no_results_body"))


class SettingsDialog(QDialog):
    def __init__(
        self,
        settings: QSettings,
        parent: QWidget | None = None,
        on_appearance_change=None,
        on_language_change=None,
    ) -> None:
        super().__init__(parent)
        self.settings = settings
        self.trn = Translator(self.settings.value("language", None, str))
        self.on_appearance_change = on_appearance_change
        self.on_language_change = on_language_change
        self.setMinimumWidth(460)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)

        form = QGridLayout()
        form.setHorizontalSpacing(18)
        form.setVerticalSpacing(12)

        self.appearance_label = _section_label("")
        form.addWidget(self.appearance_label, 0, 0, 1, 2)
        self.theme_combo = QComboBox()
        self.theme_combo.addItem("", "system")
        self.theme_combo.addItem("", "light")
        self.theme_combo.addItem("", "dark")
        _set_combo_data(self.theme_combo, self.settings.value("theme", "system", str))
        self.theme_label = QLabel()
        form.addWidget(self.theme_label, 1, 0)
        form.addWidget(self.theme_combo, 1, 1)

        self.accent_combo = QComboBox()
        self.accent_combo.addItem("", "indigo")
        self.accent_combo.addItem("", "petrol")
        self.accent_combo.addItem("", "teal")
        self.accent_combo.addItem("", "violet")
        self.accent_combo.addItem("", "slate")
        self.accent_combo.addItem("", "emerald")
        self.accent_combo.addItem("", "burgundy")
        self.accent_combo.addItem("", "amber")
        _set_combo_data(self.accent_combo, self.settings.value("accent", "indigo", str))
        self.accent_label = QLabel()
        form.addWidget(self.accent_label, 2, 0)
        form.addWidget(self.accent_combo, 2, 1)

        self.language_section_label = _section_label("")
        form.addWidget(self.language_section_label, 3, 0, 1, 2)
        self.language_combo = QComboBox()
        self.language_combo.addItem("", "system")
        self.language_combo.addItem("", "en")
        self.language_combo.addItem("", "tr")
        _set_combo_data(self.language_combo, self.settings.value("language", "system", str))
        self.language_label = QLabel()
        form.addWidget(self.language_label, 4, 0)
        form.addWidget(self.language_combo, 4, 1)

        self.behavior_label = _section_label("")
        form.addWidget(self.behavior_label, 5, 0, 1, 2)
        self.default_mode_combo = QComboBox()
        self.default_mode_combo.addItem("", "tokenized")
        self.default_mode_combo.addItem("", "tagged")
        self.default_mode_combo.addItem("", "lines")
        _set_combo_data(self.default_mode_combo, self.settings.value("default_tokenizer_mode", "tokenized", str))
        self.default_mode_label = QLabel()
        form.addWidget(self.default_mode_label, 6, 0)
        form.addWidget(self.default_mode_combo, 6, 1)

        self.remember_layout = QCheckBox()
        self.remember_layout.setChecked(self.settings.value("remember_layout", True, bool))
        form.addWidget(self.remember_layout, 7, 1)

        self.interface_label = _section_label("")
        form.addWidget(self.interface_label, 8, 0, 1, 2)
        self.density_combo = QComboBox()
        self.density_combo.addItem("", "comfortable")
        self.density_combo.addItem("", "compact")
        _set_combo_data(self.density_combo, self.settings.value("table_density", "comfortable", str))
        self.density_label = QLabel()
        form.addWidget(self.density_label, 9, 0)
        form.addWidget(self.density_combo, 9, 1)
        form.setColumnStretch(1, 1)
        layout.addLayout(form)

        self.buttons = QDialogButtonBox(QDialogButtonBox.Cancel | QDialogButtonBox.Ok)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)
        self._apply_translations()
        self.theme_combo.currentIndexChanged.connect(self._apply_appearance_immediately)
        self.accent_combo.currentIndexChanged.connect(self._apply_appearance_immediately)
        self.language_combo.currentIndexChanged.connect(self._apply_language_immediately)

    def accept(self) -> None:
        self.settings.setValue("theme", self.theme_combo.currentData())
        self.settings.setValue("accent", self.accent_combo.currentData())
        self._write_language_setting()
        self.settings.setValue("default_tokenizer_mode", self.default_mode_combo.currentData())
        self.settings.setValue("remember_layout", self.remember_layout.isChecked())
        self.settings.setValue("table_density", self.density_combo.currentData())
        super().accept()

    def _apply_appearance_immediately(self) -> None:
        self.settings.setValue("theme", self.theme_combo.currentData())
        self.settings.setValue("accent", self.accent_combo.currentData())
        if self.on_appearance_change is not None:
            self.on_appearance_change()

    def _apply_language_immediately(self) -> None:
        self._write_language_setting()
        self.trn = Translator(self.settings.value("language", None, str))
        self._apply_translations()
        if self.on_language_change is not None:
            self.on_language_change()

    def _write_language_setting(self) -> None:
        language = self.language_combo.currentData()
        if language == "system":
            self.settings.remove("language")
        else:
            self.settings.setValue("language", language)

    def _apply_translations(self) -> None:
        self.setWindowTitle(self.trn.text("settings"))
        self.appearance_label.setText(self.trn.text("appearance").upper())
        self.theme_label.setText(self.trn.text("theme"))
        self.theme_combo.setItemText(0, self.trn.text("system"))
        self.theme_combo.setItemText(1, self.trn.text("light"))
        self.theme_combo.setItemText(2, self.trn.text("dark"))
        self.accent_label.setText(self.trn.text("accent"))
        self.accent_combo.setItemText(0, self.trn.text("deep_indigo"))
        self.accent_combo.setItemText(1, self.trn.text("petrol_blue"))
        self.accent_combo.setItemText(2, self.trn.text("modern_teal"))
        self.accent_combo.setItemText(3, self.trn.text("academic_violet"))
        self.accent_combo.setItemText(4, self.trn.text("research_slate"))
        self.accent_combo.setItemText(5, self.trn.text("emerald"))
        self.accent_combo.setItemText(6, self.trn.text("burgundy"))
        self.accent_combo.setItemText(7, self.trn.text("amber"))
        self.language_section_label.setText(self.trn.text("language").upper())
        self.language_label.setText(self.trn.text("language"))
        self.language_combo.setItemText(0, self.trn.text("system"))
        self.language_combo.setItemText(1, self.trn.text("english"))
        self.language_combo.setItemText(2, self.trn.text("turkish"))
        self.behavior_label.setText(self.trn.text("behavior").upper())
        self.default_mode_label.setText(self.trn.text("default_tokenization_mode"))
        self.default_mode_combo.setItemText(0, self.trn.text("tokenized"))
        self.default_mode_combo.setItemText(1, self.trn.text("tagged"))
        self.default_mode_combo.setItemText(2, self.trn.text("lines"))
        self.remember_layout.setText(self.trn.text("remember_window_layout"))
        self.interface_label.setText(self.trn.text("interface").upper())
        self.density_label.setText(self.trn.text("table_density"))
        self.density_combo.setItemText(0, self.trn.text("comfortable"))
        self.density_combo.setItemText(1, self.trn.text("compact"))
        ok_button = self.buttons.button(QDialogButtonBox.Ok)
        cancel_button = self.buttons.button(QDialogButtonBox.Cancel)
        if ok_button is not None:
            ok_button.setText(self.trn.text("ok"))
        if cancel_button is not None:
            cancel_button.setText(self.trn.text("cancel"))


def _section_label(text: str) -> QLabel:
    label = QLabel(text.upper())
    label.setObjectName("SectionTitle")
    return label


def _set_combo_data(combo: QComboBox, value: object) -> None:
    index = combo.findData(value)
    combo.setCurrentIndex(max(index, 0))


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.settings = QSettings()
        self.trn = Translator(self.settings.value("language", None, str))
        self.tokenizer_service = TokenizerService()
        self.postagger_service = PosTaggerService()
        self.thread_pool = QThreadPool.globalInstance()
        self._workers: list[QRunnable] = []
        self.current_copy_text = ""
        self.current_headers: list[str] = []
        self.current_kind: TaskKind | None = None
        self.current_tokenizer_mode: TokenizerMode | None = None
        self.current_frequency_case_mode: FrequencyCaseMode | None = None
        self.current_elapsed_ms: int | None = None
        self._task_started_at = 0.0
        self._enforcing_splitter = False
        self._palette = palette_for(self._theme_setting(), self.settings.value("accent", "indigo", str))

        self.setWindowTitle(APP_NAME)
        self.setMinimumSize(900, 600)
        self.resize(1120, 760)
        self._build_ui()
        self._apply_theme()
        self._restore_settings()
        self._apply_translations()
        QTimer.singleShot(0, self._initialize_splitter)

    def _build_ui(self) -> None:
        root = QWidget(self)
        page = QVBoxLayout(root)
        page.setContentsMargins(0, 0, 0, 0)
        page.setSpacing(0)
        page.addWidget(self._build_header())

        body = QWidget()
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(20, 16, 20, 18)
        body_layout.setSpacing(0)

        self.splitter = QSplitter(Qt.Horizontal)
        self.splitter.setChildrenCollapsible(False)
        self.splitter.setHandleWidth(10)
        self.splitter.addWidget(self._build_input_panel())
        self.splitter.addWidget(self._build_results_panel())
        self.splitter.setStretchFactor(0, 1)
        self.splitter.setStretchFactor(1, 1)
        self.splitter.splitterMoved.connect(self._enforce_splitter_limit)
        body_layout.addWidget(self.splitter)
        page.addWidget(body, 1)
        self.setCentralWidget(root)

        self._connect_actions()

    def _build_header(self) -> QWidget:
        header = QFrame()
        header.setObjectName("AppHeader")
        header.setFixedHeight(38)
        layout = QHBoxLayout(header)
        layout.setContentsMargins(20, 4, 18, 4)
        layout.setSpacing(12)

        self.title_label = QLabel(APP_NAME)
        self.title_label.setObjectName("TitleLabel")
        self.subtitle_label = QLabel("Local Turkish NLP")
        self.subtitle_label.setObjectName("SubtitleLabel")
        self.subtitle_label.setVisible(False)
        layout.addWidget(self.title_label)
        layout.addStretch(1)

        layout.addWidget(self._build_app_menu_button())
        return header

    def _build_app_menu_button(self) -> QToolButton:
        self.app_menu_button = QToolButton()
        self.app_menu_button.setIcon(self.style().standardIcon(QStyle.SP_FileDialogDetailedView))
        self.app_menu_button.setObjectName("IconButton")
        self.app_menu_button.setPopupMode(QToolButton.InstantPopup)
        menu = QMenu(self.app_menu_button)
        self.settings_action = menu.addAction("Settings")
        menu.addSeparator()
        self.help_action = menu.addAction("Help")
        self.about_action = menu.addAction("About TS TextLab")
        menu.addSeparator()
        self.shortcuts_action = menu.addAction("Keyboard Shortcuts")
        menu.addSeparator()
        self.check_version_action = menu.addAction("Check Version")
        self.settings_action.triggered.connect(self._show_settings)
        self.help_action.triggered.connect(self._show_guide)
        self.about_action.triggered.connect(self._show_about)
        self.shortcuts_action.triggered.connect(self._show_shortcuts)
        self.check_version_action.triggered.connect(self._start_version_check)
        self.app_menu_button.setMenu(menu)
        return self.app_menu_button

    def _build_input_panel(self) -> QWidget:
        panel = QFrame()
        panel.setObjectName("Panel")
        panel.setMinimumHeight(150)
        panel.setMinimumWidth(360)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(14, 12, 14, 14)
        layout.setSpacing(10)

        top = QHBoxLayout()
        self.input_title = QLabel("INPUT")
        self.input_title.setObjectName("SectionTitle")
        self.input_meta = QLabel("0 characters · 0 spaces")
        self.input_meta.setObjectName("MetaLabel")
        top.addWidget(self.input_title)
        top.addStretch(1)
        top.addWidget(self.input_meta)
        layout.addLayout(top)

        self.input_text = QPlainTextEdit()
        self.input_text.setObjectName("InputEditor")
        self.input_text.setPlaceholderText(self.trn.text("input_placeholder"))
        self.input_text.setPlainText(DEFAULT_SAMPLE_TEXT)
        self.input_text.setMinimumHeight(82)
        layout.addWidget(self.input_text, 1)

        mode_group = QVBoxLayout()
        mode_group.setSpacing(4)
        self.tokenization_mode_label = QLabel("Tokenization Mode")
        self.tokenization_mode_label.setObjectName("MetaLabel")
        self.tokenizer_mode_combo = QComboBox()
        self.tokenizer_mode_combo.addItem("Tokenized", "tokenized")
        self.tokenizer_mode_combo.addItem("Tagged", "tagged")
        self.tokenizer_mode_combo.addItem("Lines", "lines")
        mode_group.addWidget(self.tokenization_mode_label)
        mode_group.addWidget(self.tokenizer_mode_combo)
        layout.addLayout(mode_group)

        self.actions_label = QLabel("Actions")
        self.actions_label.setObjectName("MetaLabel")
        layout.addWidget(self.actions_label)
        actions = QGridLayout()
        actions.setHorizontalSpacing(8)
        actions.setVerticalSpacing(8)
        self.tokenize_button = QPushButton("Tokenize")
        self.pos_button = QPushButton("POS Tag")
        self.frequency_button = QPushButton("Frequency")
        self.tokenize_button.setObjectName("TokenizeButton")
        self.pos_button.setObjectName("PosButton")
        self.frequency_button.setObjectName("FrequencyButton")
        for button in (self.tokenize_button, self.pos_button, self.frequency_button):
            button.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.clear_button = QToolButton()
        self.clear_button.setText("Clear")
        self.clear_button.setObjectName("UtilityButton")
        self.clear_button.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.clear_button.setPopupMode(QToolButton.InstantPopup)
        clear_menu = QMenu(self.clear_button)
        self.clear_input_action = clear_menu.addAction("Clear Input")
        self.clear_result_action = clear_menu.addAction("Clear Results")
        self.clear_all_action = clear_menu.addAction("Clear All")
        self.clear_button.setMenu(clear_menu)
        actions.addWidget(self.tokenize_button, 0, 0)
        actions.addWidget(self.pos_button, 0, 1)
        actions.addWidget(self.frequency_button, 0, 2)
        actions.addWidget(self.clear_button, 0, 3)
        actions.setColumnStretch(0, 1)
        actions.setColumnStretch(1, 1)
        actions.setColumnStretch(2, 1)
        layout.addLayout(actions)

        self.frequency_case_group = QFrame()
        self.frequency_case_group.setObjectName("ActionOptions")
        frequency_case_layout = QHBoxLayout(self.frequency_case_group)
        frequency_case_layout.setContentsMargins(0, 0, 0, 0)
        frequency_case_layout.setSpacing(8)
        self.frequency_case_label = QLabel("Frequency Case")
        self.frequency_case_label.setObjectName("MetaLabel")
        self.frequency_case_combo = QComboBox()
        self.frequency_case_combo.addItem("Case-insensitive", "insensitive")
        self.frequency_case_combo.addItem("Case-sensitive", "sensitive")
        frequency_case_layout.addWidget(self.frequency_case_label)
        frequency_case_layout.addWidget(self.frequency_case_combo, 1)
        layout.addWidget(self.frequency_case_group)
        self.frequency_case_group.setVisible(False)
        return panel

    def _build_results_panel(self) -> QWidget:
        panel = QFrame()
        panel.setObjectName("Panel")
        panel.setMinimumHeight(280)
        panel.setMinimumWidth(420)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(14, 12, 14, 14)
        layout.setSpacing(10)

        top = QHBoxLayout()
        self.results_title = QLabel("RESULTS")
        self.results_title.setObjectName("SectionTitle")
        self.results_meta = QLabel("Ready")
        self.results_meta.setObjectName("AnalysisStatus")
        top.addWidget(self.results_title)
        top.addWidget(self.results_meta)
        top.addStretch(1)
        self.filter_input = QLineEdit()
        self.filter_input.setPlaceholderText("Filter results...")
        self.filter_input.setClearButtonEnabled(True)
        self.filter_input.setMinimumWidth(260)
        self.filter_input.setMaximumWidth(360)
        top.addWidget(self.filter_input)
        self.copy_button = QToolButton()
        self.copy_button.setText("Copy")
        self.copy_button.setToolTip("Copy result")
        top.addWidget(self.copy_button)
        layout.addLayout(top)

        self.result_model = ResultTableModel(self)
        self.proxy_model = ResultProxyModel(self)
        self.proxy_model.setSourceModel(self.result_model)
        self.proxy_model.setFilterCaseSensitivity(Qt.CaseInsensitive)
        self.proxy_model.setSortRole(Qt.UserRole)

        self.table_stack = QStackedWidget()
        self.empty_state = EmptyState()
        self.results_table = QTableView()
        self.results_table.setModel(self.proxy_model)
        self.results_table.verticalHeader().setVisible(False)
        self.results_table.verticalHeader().setDefaultSectionSize(40)
        self.results_table.setAlternatingRowColors(True)
        self.results_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.results_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.results_table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.results_table.setShowGrid(False)
        self.results_table.setSortingEnabled(False)
        self.results_table.horizontalHeader().setStretchLastSection(True)
        self.results_table.horizontalHeader().setSectionsClickable(True)
        self.results_table.horizontalHeader().setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.table_stack.addWidget(self.empty_state)
        self.table_stack.addWidget(self.results_table)
        layout.addWidget(self.table_stack, 1)

        self.status_label = QLabel("Ready")
        self.status_label.setObjectName("StatusLabel")
        layout.addWidget(self.status_label)
        return panel

    def _connect_actions(self) -> None:
        self.tokenize_button.clicked.connect(lambda: self._start_task("tokenize"))
        self.pos_button.clicked.connect(lambda: self._start_task("pos"))
        self.frequency_button.clicked.connect(lambda: self._start_task("frequency"))
        self.copy_button.clicked.connect(self._copy_result)
        self.clear_input_action.triggered.connect(self.input_text.clear)
        self.clear_result_action.triggered.connect(self._clear_result)
        self.clear_all_action.triggered.connect(self._clear_all)
        self.input_text.textChanged.connect(self._update_input_meta)
        self.tokenizer_mode_combo.currentIndexChanged.connect(self._save_tokenizer_mode)
        self.frequency_case_combo.currentIndexChanged.connect(self._save_frequency_case_mode)
        self.filter_input.textChanged.connect(self._filter_results)

        QShortcut(QKeySequence("Ctrl+Return"), self, activated=lambda: self._start_task("tokenize"))
        QShortcut(QKeySequence("Meta+Return"), self, activated=lambda: self._start_task("tokenize"))
        QShortcut(QKeySequence("Ctrl+Shift+P"), self, activated=lambda: self._start_task("pos"))
        QShortcut(QKeySequence("Meta+Shift+P"), self, activated=lambda: self._start_task("pos"))
        QShortcut(QKeySequence("Ctrl+Shift+F"), self, activated=lambda: self._start_task("frequency"))
        QShortcut(QKeySequence("Meta+Shift+F"), self, activated=lambda: self._start_task("frequency"))
        QShortcut(QKeySequence("Ctrl+L"), self, activated=self._focus_input)
        QShortcut(QKeySequence("Meta+L"), self, activated=self._focus_input)
        QShortcut(QKeySequence("Ctrl+,"), self, activated=self._show_settings)
        QShortcut(QKeySequence("Meta+,"), self, activated=self._show_settings)
        QShortcut(QKeySequence.Copy, self.results_table, activated=self._copy_selection_or_result)

    def _apply_theme(self) -> None:
        app = QApplication.instance()
        if isinstance(app, QApplication):
            self._palette = apply_theme(app, self.settings)
        self._apply_density()
        self._apply_delegates()

    def _apply_density(self) -> None:
        density = self.settings.value("table_density", "comfortable", str)
        self.results_table.verticalHeader().setDefaultSectionSize(32 if density == "compact" else 40)

    def _apply_delegates(self) -> None:
        self.results_table.setItemDelegate(QStyledItemDelegate(self.results_table))
        self.results_table.setItemDelegateForColumn(2, QStyledItemDelegate(self.results_table))
        if self.current_kind == "pos":
            self.results_table.setItemDelegateForColumn(2, PosBadgeDelegate(self._palette, self.results_table))
        elif self.current_kind == "frequency":
            self.results_table.setItemDelegateForColumn(2, FrequencyBarDelegate(self._palette, self.results_table))

    def _restore_settings(self) -> None:
        if self.settings.value("remember_layout", True, bool):
            geometry = self.settings.value("window_geometry")
            if geometry:
                self.restoreGeometry(geometry)
        mode = self.settings.value("tokenizer_mode", self.settings.value("default_tokenizer_mode", "tokenized", str), str)
        if mode == "tagged_lines":
            mode = "tagged"
        _set_combo_data(self.tokenizer_mode_combo, mode)
        _set_combo_data(self.frequency_case_combo, self.settings.value("frequency_case_mode", "insensitive", str))
        self._update_input_meta()

    def _initialize_splitter(self) -> None:
        sizes = self.settings.value("splitter_sizes_horizontal") if self.settings.value("remember_layout", True, bool) else None
        if isinstance(sizes, list) and len(sizes) == 2:
            self.splitter.setSizes([int(sizes[0]), int(sizes[1])])
        else:
            width = max(1, self.splitter.width())
            self.splitter.setSizes([int(width * 0.42), int(width * 0.58)])
        self._enforce_splitter_limit()

    def _enforce_splitter_limit(self, *_args: object) -> None:
        if self._enforcing_splitter:
            return
        self._enforcing_splitter = True
        try:
            total = sum(self.splitter.sizes())
            if total <= 0:
                return
            min_input = 360
            min_result = 420
            max_input = max(min_input, int(total * 0.62))
            sizes = self.splitter.sizes()
            input_size = min(max(sizes[0], min_input), max_input)
            result_size = max(total - input_size, min_result)
            if input_size + result_size != total:
                input_size = max(min_input, total - result_size)
            if sizes != [input_size, result_size]:
                self.splitter.setSizes([input_size, result_size])
        finally:
            self._enforcing_splitter = False

    def resizeEvent(self, event) -> None:  # type: ignore[override]
        super().resizeEvent(event)
        QTimer.singleShot(0, self._enforce_splitter_limit)

    def closeEvent(self, event) -> None:  # type: ignore[override]
        if self.settings.value("remember_layout", True, bool):
            self.settings.setValue("window_geometry", self.saveGeometry())
            self.settings.setValue("splitter_sizes_horizontal", self.splitter.sizes())
        super().closeEvent(event)

    def _theme_setting(self) -> ThemeName:
        theme = self.settings.value("theme", "system", str)
        return theme if theme in {"system", "light", "dark"} else "system"  # type: ignore[return-value]

    def _start_task(self, kind: TaskKind) -> None:
        text = self.input_text.toPlainText()
        self._task_started_at = time.perf_counter()
        self.frequency_case_group.setVisible(kind == "frequency")
        self._set_busy(True, kind)
        self.status_label.setText(self.trn.text("preparing_pos") if kind == "pos" else self.trn.text("processing"))
        worker = NlpWorker(
            kind,
            text,
            self.tokenizer_mode_combo.currentData(),
            self.frequency_case_combo.currentData(),
            self.tokenizer_service,
            self.postagger_service,
        )
        worker.signals.finished.connect(self._display_result)
        worker.signals.failed.connect(self._display_error)
        self._workers.append(worker)
        self.thread_pool.start(worker)

    @Slot(object)
    def _display_result(self, result: TaskResult) -> None:
        elapsed_ms = max(1, int((time.perf_counter() - self._task_started_at) * 1000))
        result = self._localized_result(result)
        self.current_copy_text = result.copy_text
        self.current_headers = result.headers
        self.current_kind = result.kind
        self.current_tokenizer_mode = result.tokenizer_mode
        self.current_frequency_case_mode = result.frequency_case_mode
        self.current_elapsed_ms = elapsed_ms
        self.result_model.set_result(result)
        self.proxy_model.invalidateFilter()
        self.table_stack.setCurrentWidget(self.results_table)
        self.results_table.setSortingEnabled(result.kind == "frequency")
        self.frequency_case_group.setVisible(result.kind == "frequency")
        self.results_table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.results_table.setColumnWidth(0, 58)
        if result.headers:
            self.results_table.setColumnWidth(1, 280)
        if result.kind == "frequency":
            self.results_table.sortByColumn(2, Qt.DescendingOrder)
        else:
            self.proxy_model.sort(0, Qt.AscendingOrder)
        self._apply_delegates()

        label = self._kind_label(result)
        count_label = self._count_label(result.kind, len(result.rows))
        self.results_meta.setText(f"{self.trn.text('analysis')} · {label} · {count_label}")
        status = f"{self.trn.text('completed')} · {count_label} · {elapsed_ms} {self.trn.text('milliseconds')}"
        if result.kind == "tokenize" and result.tokenizer_mode == "tagged":
            status = f"{status} · {self.trn.text('tokenizer_tag_note')}"
        self.status_label.setText(status)
        self._set_busy(False)

    @Slot(str)
    def _display_error(self, message: str) -> None:
        self.status_label.setText(message)
        self.results_meta.setText(f"{self.trn.text('analysis')} · {self.trn.text('error')}")
        self._set_busy(False)

    @Slot(object)
    def _display_version_result(self, result: VersionCheckResult) -> None:
        if result.update_available:
            QMessageBox.information(
                self,
                self.trn.text("update_title"),
                self.trn.text("update_body", latest=result.latest_version, current=APP_VERSION),
            )
        elif result.checked:
            self.status_label.setText(self.trn.text("up_to_date"))
        else:
            self.status_label.setText(self.trn.text("version_check_failed"))

    def _copy_result(self) -> None:
        self._copy_selection_or_result()

    def _copy_selection_or_result(self) -> None:
        selected_text = self._selected_rows_text()
        text = selected_text or self.current_copy_text
        if not text:
            self.status_label.setText(self.trn.text("no_result"))
            return
        QGuiApplication.clipboard().setText(text)
        self.status_label.setText(self.trn.text("selection_copied") if selected_text else self.trn.text("copied"))

    def _selected_rows_text(self) -> str:
        selection = self.results_table.selectionModel()
        if selection is None or not selection.hasSelection():
            return ""
        source_rows = sorted(
            {
                self.proxy_model.mapToSource(index).row()
                for index in selection.selectedRows()
                if self.proxy_model.mapToSource(index).isValid()
            }
        )
        return self.result_model.copy_rows(source_rows)

    def _clear_result(self) -> None:
        self.current_copy_text = ""
        self.current_headers = []
        self.current_kind = None
        self.current_tokenizer_mode = None
        self.current_frequency_case_mode = None
        self.current_elapsed_ms = None
        self.result_model.set_result(None)
        self.filter_input.clear()
        self.table_stack.setCurrentWidget(self.empty_state)
        self.results_meta.setText(self.trn.text("ready"))
        self.status_label.setText(self.trn.text("cleared"))
        self.frequency_case_group.setVisible(False)

    def _clear_all(self) -> None:
        self.input_text.clear()
        self._clear_result()

    def _set_busy(self, busy: bool, kind: TaskKind | None = None) -> None:
        for button in (self.tokenize_button, self.pos_button, self.frequency_button):
            button.setDisabled(busy)
        self.clear_button.setDisabled(busy)
        self.copy_button.setDisabled(busy)
        if busy:
            text = self.trn.text("preparing_pos") if kind == "pos" else self.trn.text("processing")
            self.results_meta.setText(f"{self.trn.text('analysis')} · {text}")
            QApplication.setOverrideCursor(Qt.WaitCursor)
        else:
            QApplication.restoreOverrideCursor()

    def _apply_translations(self) -> None:
        self.input_text.setPlaceholderText(self.trn.text("input_placeholder"))
        self.subtitle_label.setText(self.trn.text("subtitle"))
        self.input_title.setText(self.trn.text("input"))
        self.results_title.setText(self.trn.text("results"))
        self.tokenization_mode_label.setText(self.trn.text("tokenization_mode"))
        self.tokenizer_mode_combo.setItemText(0, self.trn.text("tokenized"))
        self.tokenizer_mode_combo.setItemText(1, self.trn.text("tagged"))
        self.tokenizer_mode_combo.setItemText(2, self.trn.text("lines"))
        self.frequency_case_label.setText(self.trn.text("frequency_case"))
        self.frequency_case_combo.setItemText(0, self.trn.text("case_insensitive"))
        self.frequency_case_combo.setItemText(1, self.trn.text("case_sensitive"))
        self.tokenize_button.setText(self.trn.text("tokenize"))
        self.pos_button.setText(self.trn.text("pos_tag"))
        self.frequency_button.setText(self.trn.text("frequency"))
        self.actions_label.setText(self.trn.text("actions"))
        self.clear_button.setText(self.trn.text("clear"))
        self.clear_input_action.setText(self.trn.text("clear_input"))
        self.clear_result_action.setText(self.trn.text("clear_result"))
        self.clear_all_action.setText(self.trn.text("clear_all"))
        self.copy_button.setText(self.trn.text("copy"))
        self.copy_button.setToolTip(self.trn.text("copy_result"))
        self.filter_input.setPlaceholderText(self.trn.text("filter_results"))
        self.app_menu_button.setToolTip(self.trn.text("application_menu"))
        self.settings_action.setText(self.trn.text("settings"))
        self.help_action.setText(self.trn.text("help"))
        self.about_action.setText(f"{self.trn.text('about')} TS TextLab")
        self.shortcuts_action.setText(self.trn.text("keyboard_shortcuts"))
        self.check_version_action.setText(self.trn.text("check_version"))
        self.empty_state.apply_translations(self.trn)
        self._update_input_meta()
        if self.current_kind is not None:
            self.result_model.beginResetModel()
            self.result_model.headers = self._headers_for_current_result()
            self.result_model.endResetModel()
            visible = self.proxy_model.rowCount()
            self.results_meta.setText(
                f"{self.trn.text('analysis')} · {self._kind_label_from_current()} · {self._visible_count_label(visible)}"
            )
            self.status_label.setText(self._status_for_current_result())
        if not self.current_copy_text:
            self.status_label.setText(self.trn.text("ready"))

    def _start_version_check(self) -> None:
        self.status_label.setText(self.trn.text("checking_version"))
        worker = VersionWorker()
        worker.signals.finished.connect(self._display_version_result)
        self._workers.append(worker)
        self.thread_pool.start(worker)

    def _show_settings(self) -> None:
        dialog = SettingsDialog(self.settings, self, self._apply_theme, self._apply_language)
        if dialog.exec() == QDialog.Accepted:
            self._apply_theme()
            _set_combo_data(self.tokenizer_mode_combo, self.settings.value("default_tokenizer_mode", "tokenized", str))

    def _apply_language(self) -> None:
        self.trn = Translator(self.settings.value("language", None, str))
        self._apply_translations()

    def _show_about(self) -> None:
        dialog = QDialog(self)
        dialog.setWindowTitle(self.trn.text("about_title"))
        dialog.setMinimumWidth(560)
        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(22, 22, 22, 18)
        layout.setSpacing(14)

        title = QLabel(APP_NAME)
        title.setObjectName("TitleLabel")
        layout.addWidget(title)

        body = QLabel(
            f"""
            <p><b>{self.trn.text('subtitle')}</b><br>{self.trn.text('version')} {APP_VERSION}</p>
            <p><a href="https://tscorpus.com/">TS TextLab</a></p>
            <p>{self.trn.text('powered_by')}:<br>
            <a href="https://pypi.org/project/ts-tokenizer/">TS Tokenizer</a><br>
            <a href="https://github.com/tanerim/ts_SpaCy_PosTagger">TS PosTagger</a></p>
            <p>{self.trn.text('local_processing_statement')}<br>
            {self.trn.text('no_upload_statement')}</p>
            <p>SEZER, T. (2025).
            <a href="https://tez.yok.gov.tr/UlusalTezMerkezi/TezGoster?key=Xau5rw3KuCgEuy-FuJQtsNVGSOOMCSQba2T5bZaDSDUTfOiTTVCpuBZPjDrUgB0i">
            Dizilerden birimlere: Bilişimsel dilbilim çerçevesinde bir birimlendirici tasarımı</a><br>
            [Doktora tezi, HACETTEPE ÜNİVERSİTESİ]. <br> Ulusal Tez Merkezi, Tez No. 959204</p>
            """
        )
        body.setOpenExternalLinks(True)
        body.setTextFormat(Qt.RichText)
        body.setTextInteractionFlags(Qt.TextBrowserInteraction)
        body.setWordWrap(True)
        layout.addWidget(body)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok)
        buttons.accepted.connect(dialog.accept)
        layout.addWidget(buttons)
        dialog.exec()

    def _show_guide(self) -> None:
        QMessageBox.information(
            self,
            self.trn.text("guide"),
            self.trn.text("guide_body"),
        )

    def _show_shortcuts(self) -> None:
        modifier = "Cmd" if QGuiApplication.platformName() == "cocoa" else "Ctrl"
        QMessageBox.information(
            self,
            self.trn.text("keyboard_shortcuts"),
            (
                f"{modifier}+Enter    {self.trn.text('tokenize')}\n"
                f"{modifier}+Shift+P  {self.trn.text('pos_tag')}\n"
                f"{modifier}+Shift+F  {self.trn.text('frequency')}\n"
                f"{modifier}+C        {self.trn.text('copy')}\n"
                f"{modifier}+L        {self.trn.text('input')}\n"
                f"{modifier}+,        {self.trn.text('settings')}"
            ),
        )

    def _focus_input(self) -> None:
        self.input_text.setFocus()
        self.input_text.moveCursor(QTextCursor.End)

    def _filter_results(self, text: str) -> None:
        self.proxy_model.setFilterRegularExpression(QRegularExpression.escape(text))
        visible = self.proxy_model.rowCount()
        if self.result_model.rowCount():
            self.results_meta.setText(
                f"{self.trn.text('analysis')} · {self._kind_label_from_current()} · {self._visible_count_label(visible)}"
            )

    def _update_input_meta(self) -> None:
        text = self.input_text.toPlainText()
        spaces = text.count(" ")
        self.input_meta.setText(f"{len(text):,} {self.trn.text('characters')} · {spaces:,} {self.trn.text('spaces')}")

    def _save_tokenizer_mode(self) -> None:
        self.settings.setValue("tokenizer_mode", self.tokenizer_mode_combo.currentData())

    def _save_frequency_case_mode(self) -> None:
        self.settings.setValue("frequency_case_mode", self.frequency_case_combo.currentData())

    def _localized_result(self, result: TaskResult) -> TaskResult:
        return TaskResult(
            kind=result.kind,
            headers=[self._header_label(header) for header in result.headers],
            rows=result.rows,
            copy_text=result.copy_text,
            tokenizer_mode=result.tokenizer_mode,
            frequency_case_mode=result.frequency_case_mode,
        )

    def _header_label(self, header: str) -> str:
        return {
            "Token": self.trn.text("token"),
            "Tag": self.trn.text("tag"),
            "POS": self.trn.text("pos"),
            "Line": self.trn.text("line"),
            "Result": self.trn.text("result"),
            "Count": self.trn.text("count"),
        }.get(header, header)

    def _headers_for_current_result(self) -> list[str]:
        if self.current_kind == "frequency":
            return [self.trn.text("token"), self.trn.text("count")]
        if self.current_kind == "pos":
            return [self.trn.text("token"), self.trn.text("pos")]
        if self.current_kind == "tokenize":
            return {
                "tagged": [self.trn.text("token"), self.trn.text("tag")],
                "lines": [self.trn.text("line"), self.trn.text("result")],
                "tokenized": [self.trn.text("token")],
            }.get(self.current_tokenizer_mode or "tokenized", [self.trn.text("token")])
        return self.current_headers

    def _kind_label(self, result: TaskResult) -> str:
        if result.kind == "frequency":
            if result.frequency_case_mode == "sensitive":
                return self.trn.text("frequency_sensitive")
            return self.trn.text("frequency_insensitive")
        if result.kind == "pos":
            return self.trn.text("pos_tagging")
        mode = result.tokenizer_mode or "tokenized"
        return {
            "tokenized": self.trn.text("tokenization"),
            "tagged": self.trn.text("tokenizer_tags"),
            "lines": self.trn.text("line_tokenization"),
        }.get(mode, self.trn.text("tokenization"))

    def _kind_label_from_current(self) -> str:
        return {
            "frequency": self.trn.text("frequency"),
            "pos": self.trn.text("pos_tagging"),
            "tokenize": self.trn.text("tokenization"),
        }.get(self.current_kind or "", self.trn.text("results"))

    def _count_label(self, kind: TaskKind, count: int) -> str:
        noun = self.trn.text("tokens") if kind in {"tokenize", "pos"} else self.trn.text("rows")
        return f"{count:,} {noun}"

    def _visible_count_label(self, count: int) -> str:
        return f"{count:,} {self.trn.text('shown')}"

    def _status_for_current_result(self) -> str:
        count_label = self._count_label(self.current_kind or "tokenize", self.result_model.rowCount())
        elapsed_ms = self.current_elapsed_ms if self.current_elapsed_ms is not None else 0
        status = f"{self.trn.text('completed')} · {count_label} · {elapsed_ms} {self.trn.text('milliseconds')}"
        if self.current_kind == "tokenize" and self.current_tokenizer_mode == "tagged":
            status = f"{status} · {self.trn.text('tokenizer_tag_note')}"
        return status
