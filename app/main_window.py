"""PySide6 main window."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from PySide6.QtCore import (
    QAbstractTableModel,
    QModelIndex,
    QLocale,
    QObject,
    QRegularExpression,
    QRunnable,
    QRectF,
    QSettings,
    QSize,
    QSortFilterProxyModel,
    Qt,
    QThreadPool,
    QTimer,
    Signal,
    Slot,
)
from PySide6.QtGui import (
    QColor,
    QFont,
    QGuiApplication,
    QIcon,
    QKeySequence,
    QPainter,
    QPen,
    QPixmap,
    QShortcut,
    QTextCursor,
)
from PySide6.QtWidgets import (
    QAbstractItemView,
    QAbstractSpinBox,
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QPlainTextEdit,
    QProgressBar,
    QSplitter,
    QSpinBox,
    QStackedWidget,
    QStyle,
    QStyledItemDelegate,
    QTabBar,
    QTableView,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from app.analysis_service import (
    AnalysisDocument,
    AnalysisService,
    concordance_rows,
    dashboard_rows,
    frequency_rows,
    ngram_rows,
    tokenization_rows,
)
from app.config import (APP_NAME, APP_VERSION, DEFAULT_SAMPLE_TEXT, DEFAULT_MAX_INPUT_UNITS,
                        VERSION_CHECK_URL, VERSION_CHECK_INTERVAL_MS, VERSION_CHECK_RETRY_MS)
from app.dialogs import AboutDialog, NoticeDialog
from app.errors import TextLabError
from app.export_service import timestamped_csv_path, write_tab_csv
from app.i18n import Translator
from app.postagger_service import PosTaggerService, PostaggerOutputMode
from app.resource_manager import resolve_resource
from app.theme.theme_manager import LIGHT_PALETTE, ThemeName, ThemePalette, apply_theme, palette_for
from app.tokenizer_service import FrequencyCaseMode, TokenizerMode, TokenizerService
from app.version_service import VersionCheckResult, check_for_update, valid_update_url

logger = logging.getLogger(__name__)
TaskKind = Literal[
    "tokenize",
    "pos",
    "frequency",
    "ngrams",
    "concordance",
    "dashboard",
]


@dataclass(frozen=True)
class TaskResult:
    kind: TaskKind
    headers: list[str]
    rows: list[tuple[str, ...]]
    copy_text: str
    document: AnalysisDocument | None = None
    tokenizer_mode: TokenizerMode | None = None
    postagger_output_mode: PostaggerOutputMode | None = None
    frequency_case_mode: FrequencyCaseMode | None = None
    analysis_label_key: str | None = None


class WorkerSignals(QObject):
    finished = Signal(object)
    failed = Signal(str)


class VersionSignals(QObject):
    finished = Signal(object)


class VersionWorker(QRunnable):
    def __init__(self, url: str) -> None:
        super().__init__()
        self.setAutoDelete(False)
        self.signals = VersionSignals()
        self.url = url

    @Slot()
    def run(self) -> None:
        result = check_for_update(self.url)
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
        postagger_output_mode: PostaggerOutputMode,
        frequency_case_mode: FrequencyCaseMode,
        ngram_n: int,
        ngram_types: set[str],
        concordance_query: str,
        concordance_span: int,
        existing_document: AnalysisDocument | None,
        tokenizer_service: TokenizerService,
        postagger_service: PosTaggerService,
    ) -> None:
        super().__init__()
        self.setAutoDelete(False)
        self.kind = kind
        self.text = text
        self.tokenizer_mode = tokenizer_mode
        self.postagger_output_mode = postagger_output_mode
        self.frequency_case_mode = frequency_case_mode
        self.ngram_n = ngram_n
        self.ngram_types = ngram_types
        self.concordance_query = concordance_query
        self.concordance_span = concordance_span
        self.existing_document = existing_document
        self.tokenizer_service = tokenizer_service
        self.postagger_service = postagger_service
        self.analysis_service = AnalysisService(tokenizer_service, postagger_service)
        self.signals = WorkerSignals()

    @Slot()
    def run(self) -> None:
        try:
            if self.kind == "pos":
                headers, rows, copy_text = self.postagger_service.format_output(self.text, self.postagger_output_mode)
                result = TaskResult(
                    self.kind,
                    headers,
                    rows,
                    copy_text,
                    postagger_output_mode=self.postagger_output_mode,
                    analysis_label_key="pos_tagging",
                )
                self.signals.finished.emit(result)
                return

            include_pos = self.kind == "dashboard"
            if include_pos:
                document = self.analysis_service.build_document(self.text, include_pos=True)
            elif self.existing_document is not None:
                document = self.existing_document
            else:
                document = self.analysis_service.build_document(self.text)
            if self.kind == "tokenize":
                headers, rows, copy_text = tokenization_rows(document, self.tokenizer_mode)
                result = TaskResult(self.kind, headers, rows, copy_text, document, self.tokenizer_mode)
            elif self.kind == "frequency":
                headers, rows, copy_text = frequency_rows(
                    document, self.frequency_case_mode, self.tokenizer_service._char_fix.tr_lowercase
                )
                result = TaskResult(self.kind, headers, rows, copy_text, document, frequency_case_mode=self.frequency_case_mode)
            elif self.kind == "ngrams":
                headers, rows, copy_text = ngram_rows(document, self.ngram_n, self.ngram_types)
                result = TaskResult(self.kind, headers, rows, copy_text, document)
            elif self.kind == "concordance":
                headers, rows, copy_text = concordance_rows(document, self.concordance_query, self.concordance_span)
                result = TaskResult(self.kind, headers, rows, copy_text, document)
            elif self.kind == "dashboard":
                headers, rows, copy_text = dashboard_rows(self.text, document)
                result = TaskResult(self.kind, headers, rows, copy_text, document)
            else:
                raise TextLabError(f"Bilinmeyen analiz türü: {self.kind}")
            self.signals.finished.emit(result)
        except TextLabError as exc:
            logger.warning("NLP task failed: %s", exc)
            self.signals.failed.emit(str(exc))
        except Exception as exc:  # pragma: no cover - GUI boundary guard
            logger.exception("Unexpected NLP task failure")
            self.signals.failed.emit(f"Beklenmeyen bir hata oluştu: {exc}")
        finally:
            self.text = ""
            self.existing_document = None


class ResultTableModel(QAbstractTableModel):
    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.kind: TaskKind | None = None
        self.headers: list[str] = []
        self.rows: list[tuple[str, ...]] = []
        self.frequency_max = 1.0

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
        self.frequency_max = max((float(row[1]) for row in self.rows if len(row) > 1), default=1.0) if self.kind in {"frequency", "ngrams"} else 1.0
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

        if role == Qt.ToolTipRole and column > 0:
            value_index = column - 1
            return self.rows[row][value_index] if value_index < len(self.rows[row]) else ""

        if role == Qt.TextAlignmentRole:
            value_index = column - 1
            value = self.rows[row][value_index] if value_index < len(self.rows[row]) else ""
            if self.kind == "concordance":
                if column == 1:
                    return int(Qt.AlignRight | Qt.AlignVCenter)
                if column == 2:
                    return int(Qt.AlignCenter)
                if column == 3:
                    return int(Qt.AlignLeft | Qt.AlignVCenter)
            if column == 0 or _is_number_like(value):
                return int(Qt.AlignRight | Qt.AlignVCenter)
            return int(Qt.AlignLeft | Qt.AlignVCenter)

        if role == Qt.UserRole:
            if column == 0:
                return row + 1
            value_index = column - 1
            value = self.rows[row][value_index] if value_index < len(self.rows[row]) else ""
            numeric = _numeric_value(value)
            if numeric is not None:
                return numeric
            return value.casefold()

        return None

    def headerData(self, section: int, orientation: Qt.Orientation, role: int = Qt.DisplayRole) -> object:
        if orientation != Qt.Horizontal:
            return None
        if role == Qt.TextAlignmentRole and self.kind == "concordance":
            return int(Qt.AlignCenter)
        if role != Qt.DisplayRole:
            return None
        if section == 0:
            return "#"
        return self.headers[section - 1] if section - 1 < len(self.headers) else ""

    def copy_rows(self, source_rows: list[int] | None = None) -> str:
        rows = self.rows if source_rows is None else [self.rows[row] for row in source_rows if row < len(self.rows)]
        return "\n".join("\t".join(row) for row in rows)


class ResultProxyModel(QSortFilterProxyModel):
    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.filter_text = ""

    def set_filter_text(self, text: str) -> None:
        self.filter_text = text
        self.setFilterRegularExpression(QRegularExpression.escape(text))

    def filterAcceptsRow(self, source_row: int, source_parent: QModelIndex) -> bool:
        if not self.filter_text:
            return True
        model = self.sourceModel()
        if model is None:
            return True
        text = self.filter_text.casefold()
        if getattr(model, "kind", None) == "ngrams":
            value = model.index(source_row, 1, source_parent).data(Qt.DisplayRole)
            return _contains_token_query(str(value), text)
        for column in range(1, model.columnCount()):
            value = model.index(source_row, column, source_parent).data(Qt.DisplayRole)
            if text in str(value).casefold():
                return True
        return False

    def lessThan(self, left: QModelIndex, right: QModelIndex) -> bool:
        left_value = left.data(Qt.UserRole)
        right_value = right.data(Qt.UserRole)
        if isinstance(left_value, (int, float)) and isinstance(right_value, (int, float)):
            return left_value < right_value
        return str(left_value) < str(right_value)


class PosBadgeDelegate(QStyledItemDelegate):
    LIGHT_COLORS = {
        "NOUN": ("#EAF1F8", "#2F5577"),
        "PROPN": ("#EFEFFA", "#514D82"),
        "VERB": ("#EAF5EE", "#316047"),
        "AUX": ("#E9F3F1", "#315F58"),
        "ADJ": ("#F7F0E4", "#775C30"),
        "ADV": ("#F7EAF0", "#765169"),
        "DET": ("#EAF4F6", "#35606A"),
        "PRON": ("#F0ECF7", "#624F78"),
        "ADP": ("#F1F3F6", "#4D5968"),
        "CCONJ": ("#F3EDF3", "#6A5268"),
        "SCONJ": ("#F3EDF3", "#6A5268"),
        "NUM": ("#F6EEE9", "#76533F"),
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

    def __init__(self, palette: ThemePalette, column: int = 2, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.palette = palette
        self.column = column

    def paint(self, painter: QPainter, option, index: QModelIndex) -> None:  # type: ignore[override]
        if index.column() != self.column:
            super().paint(painter, option, index)
            return

        painter.save()
        if option.state & QStyle.State_Selected:
            painter.fillRect(option.rect, option.palette.highlight())
        text = str(index.data(Qt.DisplayRole) or "")
        rect = option.rect.adjusted(8, 6, -8, -6)
        width = min(rect.width(), option.fontMetrics.horizontalAdvance(text) + 16)
        badge = QRectF(rect.left(), rect.top(), width, rect.height())
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(Qt.NoPen)
        bg, fg = self._colors_for(text)
        painter.setBrush(QColor(bg))
        painter.drawRoundedRect(badge, 5, 5)
        painter.setPen(QPen(QColor(fg)))
        painter.drawText(badge, Qt.AlignCenter, text)
        painter.restore()

    def _colors_for(self, text: str) -> tuple[str, str]:
        key = text.strip().upper().split(":", 1)[0].split("-", 1)[0]
        colors = self.DARK_COLORS if self.palette.name == "dark" else self.LIGHT_COLORS
        return colors.get(key, (self.palette.pos_badge_bg, self.palette.pos_badge_text))


class FrequencyBarDelegate(QStyledItemDelegate):
    def __init__(self, palette: ThemePalette, column: int = 2, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.palette = palette
        self.column = column

    def paint(self, painter: QPainter, option, index: QModelIndex) -> None:  # type: ignore[override]
        if index.column() != self.column:
            super().paint(painter, option, index)
            return

        model = index.model()
        source = model.sourceModel() if isinstance(model, QSortFilterProxyModel) else model
        max_value = max(1.0, source.frequency_max)

        painter.save()
        if option.state & QStyle.State_Selected:
            painter.fillRect(option.rect, option.palette.highlight())
        display_text = str(index.data(Qt.DisplayRole) or "")
        value = _numeric_value(display_text) or 0
        track = option.rect.adjusted(10, 14, -62, -14)
        if track.width() > 24:
            fill = QRectF(track)
            fill.setWidth(max(3, track.width() * float(value) / max_value))
            painter.setRenderHint(QPainter.Antialiasing)
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(self.palette.bar_fill))
            painter.drawRoundedRect(fill, 3, 3)
        painter.setPen(QPen(QColor(self.palette.text)))
        painter.drawText(option.rect.adjusted(0, 0, -14, 0), Qt.AlignRight | Qt.AlignVCenter, display_text)
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


class WatermarkedPlainTextEdit(QPlainTextEdit):
    def __init__(self, logo: QPixmap, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.logo = logo

    def paintEvent(self, event) -> None:  # type: ignore[override]
        super().paintEvent(event)
        if self.logo.isNull():
            return
        viewport_rect = self.viewport().rect()
        target_width = min(int(viewport_rect.width() * 0.62), 360)
        if target_width <= 0:
            return
        target_height = int(target_width * self.logo.height() / max(1, self.logo.width()))
        scaled = self.logo.scaled(target_width, target_height, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        x = viewport_rect.center().x() - scaled.width() // 2
        y = viewport_rect.center().y() - scaled.height() // 2
        painter = QPainter(self.viewport())
        painter.setOpacity(0.10)
        painter.drawPixmap(x, y, scaled)
        painter.end()


class AnalysisDashboard(QWidget):
    BAR_COLORS = ["#0D6EFD", "#20C997", "#6F42C1", "#FD7E14", "#198754", "#0DCAF0", "#D63384", "#FFC107"]

    def __init__(self) -> None:
        super().__init__()
        self.result: TaskResult | None = None
        self.trn: Translator | None = None
        self.palette: ThemePalette | None = None
        self.setMinimumWidth(300)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setFixedHeight(self._report_height())

    def _report_height(self) -> int:
        return 44 + 6 * 68 + 5 * 10 + 18 + 616 + 408

    def set_result(self, result: TaskResult | None, trn: Translator, palette: ThemePalette) -> None:
        self.result = result
        self.trn = trn
        self.palette = palette
        self.update()

    def paintEvent(self, _event) -> None:  # type: ignore[override]
        painter = QPainter(self)
        try:
            painter.setRenderHint(QPainter.Antialiasing)
            self._paint_report(painter, QRectF(0, 0, self.width(), self.height()))
        finally:
            painter.end()

    def _paint_report(self, painter: QPainter, rect: QRectF) -> None:
        palette = self.palette or LIGHT_PALETTE
        painter.fillRect(rect, QColor("#F4F7FB"))
        result = self.result
        if result is None:
            return

        metrics, token_types, pos_counts = self._sections(result.rows)
        margin = 22
        x = rect.left() + margin
        y = rect.top() + margin
        width = rect.width() - margin * 2

        y = self._draw_metric_cards(painter, x, y, width, metrics, palette)
        y += 18
        chart_gap = 16
        chart_width = width
        chart_height = 292
        self._draw_bar_panel(painter, QRectF(x, y, chart_width, chart_height), self._text("distribution"), token_types, palette)
        chart_x = x
        chart_y = y + chart_height + chart_gap
        self._draw_bar_panel(painter, QRectF(chart_x, chart_y, chart_width, chart_height), self._text("pos_distribution"), pos_counts, palette)
        y += (chart_height + 16) * 2
        summary_width = width
        self._draw_summary_panel(painter, QRectF(x, y, summary_width, 196), metrics, palette)
        self._draw_highlights_panel(
            painter,
            QRectF(x, y + 212, summary_width, 196),
            metrics,
            token_types,
            pos_counts,
            palette,
        )

    def _draw_metric_cards(
        self, painter: QPainter, x: float, y: float, width: float, metrics: dict[str, str], palette: ThemePalette
    ) -> float:
        keys = ["Characters", "Tokens", "Lexical tokens", "Unique tokens", "Sentences", "Type-token ratio"]
        row_height = 68
        gap = 10
        for index, key in enumerate(keys):
            rect = QRectF(x, y + index * (row_height + gap), width, row_height)
            self._dashboard_panel(painter, rect)
            accent = QColor(self.BAR_COLORS[index % len(self.BAR_COLORS)])
            painter.setPen(Qt.NoPen)
            painter.setBrush(accent)
            painter.drawRoundedRect(QRectF(rect.left(), rect.top(), 4, rect.height()), 2, 2)
            self._draw_metric_icon(painter, QRectF(rect.left() + 16, rect.top() + 20, 28, 28), key, accent.name())
            painter.setPen(QColor("#334155"))
            self._fit_text(painter, QRectF(rect.left() + 56, rect.top() + 12, width - 188, 22), self._metric_label(key), 11, 9, bold=True)
            painter.setPen(QColor("#64748B"))
            self._fit_text(painter, QRectF(rect.left() + 56, rect.top() + 36, width - 188, 18), self._metric_hint(key), 9, 8)
            painter.setPen(QColor("#111827"))
            self._fit_text(painter, QRectF(rect.right() - 124, rect.top() + 14, 108, 40), metrics.get(key, "0"), 25, 15, bold=True, align=Qt.AlignRight | Qt.AlignVCenter)
        return y + len(keys) * row_height + (len(keys) - 1) * gap

    def _draw_bar_panel(
        self, painter: QPainter, rect: QRectF, title: str, values: list[tuple[str, int]], palette: ThemePalette
    ) -> None:
        self._dashboard_panel(painter, rect)
        painter.setPen(QColor("#111827"))
        self._fit_text(painter, rect.adjusted(16, 12, -16, -250), title, 13, 10, bold=True)

        top_values = values[:8]
        max_value = max([value for _, value in top_values] or [1])
        y = rect.top() + 52
        for index, (label, value) in enumerate(top_values):
            row_top = y + index * 30
            painter.setPen(QColor("#64748B"))
            self._fit_text(painter, QRectF(rect.left() + 16, row_top, rect.width() - 106, 15), self._metric_label(label), 10, 8)
            bar_rect = QRectF(rect.left() + 16, row_top + 17, rect.width() - 104, 7)
            value_rect = QRectF(bar_rect.right() + 10, row_top + 10, 56, 20)
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor("#E9EEF6"))
            painter.drawRoundedRect(bar_rect, 4, 4)
            fill = QRectF(bar_rect)
            fill.setWidth(max(8, bar_rect.width() * value / max_value))
            painter.setBrush(QColor(self.BAR_COLORS[index % len(self.BAR_COLORS)]))
            painter.drawRoundedRect(fill, 4, 4)
            painter.setPen(QColor("#475569"))
            self._fit_text(painter, value_rect, str(value), 11, 9, bold=True, align=Qt.AlignRight | Qt.AlignVCenter)

    def _draw_summary_panel(self, painter: QPainter, rect: QRectF, metrics: dict[str, str], palette: ThemePalette) -> None:
        self._dashboard_panel(painter, rect)
        painter.setPen(QColor("#111827"))
        self._fit_text(painter, rect.adjusted(16, 12, -16, -158), self._text("text_profile"), 13, 10, bold=True)
        rows = [
            (self._metric_label("Sentences"), metrics.get("Sentences", "0")),
            (self._metric_label("Lexical tokens"), metrics.get("Lexical tokens", "0")),
            (self._metric_label("Unique tokens"), metrics.get("Unique tokens", "0")),
            (self._metric_label("Mean token length"), metrics.get("Mean token length", "0")),
            (self._metric_label("Type-token ratio"), metrics.get("Type-token ratio", "0")),
        ]
        row_y = rect.top() + 44
        for label, value in rows:
            self._draw_stat_row(painter, QRectF(rect.left() + 16, row_y, rect.width() - 32, 25), label, value, palette)
            row_y += 29

    def _draw_highlights_panel(
        self,
        painter: QPainter,
        rect: QRectF,
        metrics: dict[str, str],
        token_types: list[tuple[str, int]],
        pos_counts: list[tuple[str, int]],
        palette: ThemePalette,
    ) -> None:
        self._dashboard_panel(painter, rect)
        painter.setPen(QColor("#111827"))
        self._fit_text(painter, rect.adjusted(16, 12, -16, -158), self._text("more_info"), 13, 10, bold=True)
        lines = [
            (self._text("top_token_type"), self._top_label(token_types)),
            (self._text("top_pos"), self._top_label(pos_counts)),
            (self._text("lexical_share"), self._share(metrics, "Lexical tokens", "Tokens")),
            (self._text("vocabulary_spread"), self._share(metrics, "Unique tokens", "Lexical tokens")),
        ]
        row_y = rect.top() + 44
        for label, value in lines:
            self._draw_stat_row(painter, QRectF(rect.left() + 16, row_y, rect.width() - 32, 25), label, value, palette)
            row_y += 29

    def _rounded_panel(self, painter: QPainter, rect: QRectF, background: str, border: str) -> None:
        painter.setPen(QPen(QColor(border), 1))
        painter.setBrush(QColor(background))
        painter.drawRoundedRect(rect, 8, 8)

    def _soft_panel(self, painter: QPainter, rect: QRectF, palette: ThemePalette) -> None:
        painter.setPen(QPen(QColor(palette.border), 1))
        painter.setBrush(QColor(palette.surface))
        painter.drawRoundedRect(rect, 8, 8)

    def _dashboard_panel(self, painter: QPainter, rect: QRectF) -> None:
        painter.save()
        painter.setPen(QPen(QColor("#DDE5F0"), 1))
        painter.setBrush(QColor("#FFFFFF"))
        painter.drawRoundedRect(rect, 8, 8)
        painter.restore()

    def _draw_metric_icon(self, painter: QPainter, rect: QRectF, key: str, color: str) -> None:
        painter.save()
        painter.setPen(Qt.NoPen)
        icon_bg = QColor(color)
        icon_bg.setAlpha(32)
        painter.setBrush(icon_bg)
        painter.drawRoundedRect(rect, 7, 7)
        glyph = {
            "Characters": "Aa",
            "Tokens": "Tk",
            "Lexical tokens": "Lx",
            "Unique tokens": "Uq",
            "Sentences": "Ss",
            "Type-token ratio": "Tr",
        }.get(key, "..")
        painter.setPen(QColor(color))
        self._fit_text(painter, rect, glyph, 10, 7, bold=True)
        painter.restore()

    def _draw_stat_row(self, painter: QPainter, rect: QRectF, label: str, value: str, palette: ThemePalette) -> None:
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor("#F8FAFC"))
        painter.drawRoundedRect(rect, 7, 7)
        painter.setPen(QColor("#64748B"))
        self._fit_text(painter, rect.adjusted(10, 0, -96, 0), label, 9, 8, bold=True)
        painter.setPen(QColor("#111827"))
        self._fit_text(painter, rect.adjusted(rect.width() - 92, 0, -10, 0), value, 11, 9, bold=True, align=Qt.AlignRight | Qt.AlignVCenter)

    def _fit_text(
        self,
        painter: QPainter,
        rect: QRectF,
        text: str,
        max_size: int,
        min_size: int,
        bold: bool = False,
        align: Qt.AlignmentFlag = Qt.AlignLeft | Qt.AlignVCenter,
    ) -> None:
        for size in range(max_size, min_size - 1, -1):
            font = QFont()
            font.setPointSize(size)
            font.setBold(bold)
            painter.setFont(font)
            if painter.fontMetrics().horizontalAdvance(text) <= rect.width():
                painter.drawText(rect, align, text)
                return
        font = QFont()
        font.setPointSize(min_size)
        font.setBold(bold)
        painter.setFont(font)
        painter.drawText(rect, align, text)

    def _sections(self, rows: list[tuple[str, ...]]) -> tuple[dict[str, str], list[tuple[str, int]], list[tuple[str, int]]]:
        metrics: dict[str, str] = {}
        token_types: list[tuple[str, int]] = []
        pos_counts: list[tuple[str, int]] = []
        for row in rows:
            if len(row) < 3:
                continue
            section, label, value = row[0], row[1], row[2]
            if section == "Metric":
                metrics[label] = value
            elif section == "Token Type":
                token_types.append((label, int(float(value))))
            elif section == "POS":
                pos_counts.append((label, int(float(value))))
        return metrics, token_types, pos_counts

    def _text(self, key: str) -> str:
        return self.trn.text(key) if self.trn is not None else key

    def _metric_label(self, label: str) -> str:
        mapping = {
            "Characters": "characters_measure",
            "Tokens": "tokens_measure",
            "Lexical tokens": "lexical_tokens",
            "Unique tokens": "unique_tokens",
            "Sentences": "sentences",
            "Mean token length": "mean_token_length",
            "Type-token ratio": "type_token_ratio",
            "Words": "words",
            "Punctuation": "punctuation",
            "URLs": "urls",
            "Mentions": "mentions",
            "Hashtags": "hashtags",
            "XML_Tag": "xml_tags",
        }
        key = mapping.get(label)
        return self._text(key) if key else label

    def _metric_hint(self, label: str) -> str:
        return {
            "Characters": self._text("characters"),
            "Tokens": self._text("tokens"),
            "Lexical tokens": self._text("lexical_tokens"),
            "Unique tokens": self._text("unique_tokens"),
            "Sentences": self._text("sentence_count"),
            "Type-token ratio": self._text("distribution"),
        }.get(label, "")

    def _headline(self, metrics: dict[str, str]) -> str:
        return (
            f"{metrics.get('Tokens', '0')} {self._text('tokens')} · "
            f"{metrics.get('Sentences', '0')} {self._text('sentences')} · "
            f"{metrics.get('Unique tokens', '0')} {self._text('unique_tokens')}"
        )

    def _top_label(self, values: list[tuple[str, int]]) -> str:
        if not values:
            return "-"
        label, count = values[0]
        return f"{self._metric_label(label)} ({count})"

    def _share(self, metrics: dict[str, str], numerator_key: str, denominator_key: str) -> str:
        numerator = _numeric_value(metrics.get(numerator_key, "0")) or 0
        denominator = _numeric_value(metrics.get(denominator_key, "0")) or 0
        if denominator <= 0:
            return "0%"
        return f"{(numerator / denominator) * 100:.1f}%"


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
        self.setMinimumWidth(600)
        self.resize(660, 740)

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setObjectName("SettingsScroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        content = QWidget()
        scroll.setWidget(content)
        root_layout.addWidget(scroll, 1)
        layout = QVBoxLayout(content)
        layout.setContentsMargins(28, 26, 28, 8)
        layout.setSpacing(18)

        self.title_label = QLabel()
        self.title_label.setObjectName("DialogTitle")
        layout.addWidget(self.title_label)

        self.subtitle = QLabel()
        self.subtitle.setObjectName("DialogMuted")
        self.subtitle.setWordWrap(True)
        layout.addWidget(self.subtitle)

        language_card = QFrame()
        language_card.setObjectName("DialogCard")
        form = QGridLayout(language_card)
        form.setContentsMargins(20, 18, 20, 18)
        form.setHorizontalSpacing(24)
        form.setVerticalSpacing(14)

        self.language_section_label = _section_label("")
        form.addWidget(self.language_section_label, 0, 0, 1, 2)
        self.language_combo = QComboBox()
        self.language_combo.addItem("", "system")
        self.language_combo.addItem("", "en")
        self.language_combo.addItem("", "tr")
        _set_combo_data(self.language_combo, self.settings.value("language", "system", str))
        self.language_label = QLabel()
        form.addWidget(self.language_label, 1, 0)
        form.addWidget(self.language_combo, 1, 1)

        form.setColumnStretch(1, 1)
        layout.addWidget(language_card)

        behavior_card = QFrame()
        behavior_card.setObjectName("DialogCard")
        form = QGridLayout(behavior_card)
        form.setContentsMargins(20, 18, 20, 18)
        form.setHorizontalSpacing(24)
        form.setVerticalSpacing(14)
        self.behavior_label = _section_label("")
        form.addWidget(self.behavior_label, 0, 0, 1, 2)
        self.default_mode_combo = QComboBox()
        self.default_mode_combo.addItem("", "tokenized")
        self.default_mode_combo.addItem("", "tagged")
        self.default_mode_combo.addItem("", "lines")
        _set_combo_data(self.default_mode_combo, self.settings.value("default_tokenizer_mode", "tokenized", str))
        self.default_mode_label = QLabel()
        self.default_mode_label.setWordWrap(True)
        form.addWidget(self.default_mode_label, 1, 0)
        form.addWidget(self.default_mode_combo, 1, 1)

        self.remember_layout = QCheckBox()
        self.remember_layout.setChecked(self.settings.value("remember_layout", True, bool))
        form.addWidget(self.remember_layout, 2, 0, 1, 2)
        form.setColumnStretch(0, 1)
        form.setColumnStretch(1, 1)
        layout.addWidget(behavior_card)

        capacity_card = QFrame()
        capacity_card.setObjectName("CapacityCard")
        capacity = QVBoxLayout(capacity_card)
        capacity.setContentsMargins(20, 18, 20, 18)
        capacity.setSpacing(10)
        self.limit_label = _section_label("")
        capacity.addWidget(self.limit_label)
        self.limit_hint = QLabel()
        self.limit_hint.setObjectName("DialogMuted")
        self.limit_hint.setWordWrap(True)
        capacity.addWidget(self.limit_hint)
        self.limit_spin = QSpinBox()
        self.limit_spin.setObjectName("CapacityInput")
        self.limit_spin.setButtonSymbols(QAbstractSpinBox.NoButtons)
        self.limit_spin.setRange(1, 2_147_483_647)
        self.limit_spin.setGroupSeparatorShown(True)
        self.limit_spin.setValue(self.settings.value("max_input_units", DEFAULT_MAX_INPUT_UNITS, int))
        capacity.addWidget(self.limit_spin)
        presets = QHBoxLayout()
        self.limit_presets = []
        for value in (1_000_000, 2_000_000, 5_000_000):
            button = QPushButton()
            button.setObjectName("LimitPreset")
            button.setCheckable(True)
            button.clicked.connect(lambda checked=False, selected=value: self._choose_limit(selected))
            presets.addWidget(button)
            self.limit_presets.append((value, button))
        capacity.addLayout(presets)
        self.limit_spin.valueChanged.connect(self._sync_limit_presets)
        self._sync_limit_presets()
        layout.addWidget(capacity_card)

        interface_card = QFrame()
        interface_card.setObjectName("DialogCard")
        form = QGridLayout(interface_card)
        form.setContentsMargins(20, 18, 20, 18)
        form.setHorizontalSpacing(24)
        form.setVerticalSpacing(14)

        self.interface_label = _section_label("")
        form.addWidget(self.interface_label, 0, 0, 1, 2)
        self.density_combo = QComboBox()
        self.density_combo.addItem("", "comfortable")
        self.density_combo.addItem("", "compact")
        _set_combo_data(self.density_combo, self.settings.value("table_density", "comfortable", str))
        self.density_label = QLabel()
        form.addWidget(self.density_label, 1, 0)
        form.addWidget(self.density_combo, 1, 1)
        form.setColumnStretch(1, 1)
        layout.addWidget(interface_card)

        updates_card = QFrame()
        updates_card.setObjectName("DialogCard")
        updates = QVBoxLayout(updates_card)
        updates.setContentsMargins(20, 18, 20, 18)
        updates.setSpacing(10)
        self.updates_label = _section_label("")
        self.updates_hint = QLabel()
        self.updates_hint.setObjectName("DialogMuted")
        self.updates_hint.setWordWrap(True)
        self.update_url = QLineEdit(self.settings.value("update_url", VERSION_CHECK_URL, str))
        self.update_url.setPlaceholderText("https://…/updates.json")
        updates.addWidget(self.updates_label)
        updates.addWidget(self.updates_hint)
        updates.addWidget(self.update_url)
        layout.addWidget(updates_card)
        layout.addStretch(1)

        self.buttons = QDialogButtonBox(QDialogButtonBox.Cancel | QDialogButtonBox.Ok)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        footer = QFrame()
        footer.setObjectName("DialogFooter")
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(28, 12, 28, 14)
        footer_layout.addStretch(1)
        footer_layout.addWidget(self.buttons)
        root_layout.addWidget(footer)
        self._apply_translations()
        self.language_combo.currentIndexChanged.connect(self._apply_language_immediately)

    def accept(self) -> None:
        self.limit_spin.interpretText()
        limit = self.limit_spin.value()
        url = self.update_url.text().strip()
        if url and not valid_update_url(url):
            NoticeDialog(self.trn, self.trn.text("updates"), self.trn.text("update_url_invalid"), self).exec()
            self.update_url.setFocus()
            return
        if limit > DEFAULT_MAX_INPUT_UNITS and limit != self.settings.value("max_input_units", DEFAULT_MAX_INPUT_UNITS, int):
            confirmation = NoticeDialog(self.trn, self.trn.text("limit_confirm_title"),
                self.trn.text("limit_confirm"), self,
                detail=self.limit_spin.text() + " " + self.trn.text("units"),
                confirm=self.trn.text("use_limit"))
            if confirmation.exec() != QDialog.Accepted:
                return
        self.settings.setValue("update_url", url)
        self.settings.setValue("max_input_units", limit)
        self.settings.setValue("theme", "light")
        self.settings.setValue("accent", "indigo")
        self._write_language_setting()
        self.settings.setValue("default_tokenizer_mode", self.default_mode_combo.currentData())
        self.settings.setValue("remember_layout", self.remember_layout.isChecked())
        self.settings.setValue("table_density", self.density_combo.currentData())
        super().accept()

    def _choose_limit(self, value: int) -> None:
        self.limit_spin.setValue(value)
        self._sync_limit_presets()

    def _sync_limit_presets(self) -> None:
        for value, button in self.limit_presets:
            button.setChecked(self.limit_spin.value() == value)

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
        self.title_label.setText(self.trn.text("settings"))
        self.subtitle.setText(self.trn.text("settings_hint"))
        self.language_section_label.setText(self.trn.text("language"))
        self.language_label.setText(self.trn.text("language"))
        self.language_combo.setItemText(0, self.trn.text("system"))
        self.language_combo.setItemText(1, self.trn.text("english"))
        self.language_combo.setItemText(2, self.trn.text("turkish"))
        self.limit_spin.setLocale(QLocale("tr_TR" if self.trn.language == "tr" else "en_US"))
        self.limit_label.setText(self.trn.text("max_input_units"))
        self.limit_hint.setText(self.trn.text("limit_hint"))
        self.limit_spin.setAccessibleName(self.trn.text("max_input_units"))
        for value, button in self.limit_presets:
            button.setText(self.trn.text("million_units", count=value // 1_000_000))
        self.updates_label.setText(self.trn.text("updates"))
        self.updates_hint.setText(self.trn.text("updates_hint"))
        self.update_url.setAccessibleName(self.trn.text("update_source"))
        self.behavior_label.setText(self.trn.text("behavior"))
        self.default_mode_label.setText(self.trn.text("default_tokenization_mode"))
        self.default_mode_combo.setItemText(0, self.trn.text("tokenized"))
        self.default_mode_combo.setItemText(1, self.trn.text("tagged"))
        self.default_mode_combo.setItemText(2, self.trn.text("lines"))
        self.remember_layout.setText(self.trn.text("remember_window_layout"))
        self.interface_label.setText(self.trn.text("interface"))
        self.density_label.setText(self.trn.text("table_density"))
        self.density_combo.setItemText(0, self.trn.text("comfortable"))
        self.density_combo.setItemText(1, self.trn.text("compact"))
        ok_button = self.buttons.button(QDialogButtonBox.Ok)
        cancel_button = self.buttons.button(QDialogButtonBox.Cancel)
        if ok_button is not None:
            ok_button.setText(self.trn.text("ok"))
        if cancel_button is not None:
            cancel_button.setText(self.trn.text("cancel"))
        _style_dialog_buttons(self.buttons)


def _section_label(text: str) -> QLabel:
    label = QLabel(text)
    label.setObjectName("DialogSection")
    return label


def _style_dialog_buttons(buttons: QDialogButtonBox) -> None:
    ok_button = buttons.button(QDialogButtonBox.Ok)
    cancel_button = buttons.button(QDialogButtonBox.Cancel)
    if ok_button is not None:
        ok_button.setObjectName("DialogPrimaryButton")
    if cancel_button is not None:
        cancel_button.setObjectName("DialogSecondaryButton")
    for button in (ok_button, cancel_button):
        if button is not None:
            button.style().unpolish(button)
            button.style().polish(button)


def _set_combo_data(combo: QComboBox, value: object) -> None:
    index = combo.findData(value)
    combo.setCurrentIndex(max(index, 0))


def _numeric_value(value: str) -> float | None:
    try:
        cleaned = value.strip()
        if cleaned.endswith("%"):
            cleaned = cleaned[:-1]
        return float(cleaned.replace(",", ""))
    except ValueError:
        return None


def _is_number_like(value: str) -> bool:
    return _numeric_value(value) is not None


def _contains_token_query(value: str, query: str) -> bool:
    query_tokens = [token for token in query.casefold().split() if token]
    if not query_tokens:
        return True
    value_tokens = [token for token in value.casefold().split() if token]
    if len(query_tokens) == 1:
        return query_tokens[0] in value_tokens
    query_length = len(query_tokens)
    return any(value_tokens[index : index + query_length] == query_tokens for index in range(len(value_tokens)))


class MainWindow(QMainWindow):
    def __init__(self, enable_update_checks: bool = True) -> None:
        super().__init__()
        self.settings = QSettings()
        if self.settings.value("update_url", "", str) == "https://raw.githubusercontent.com/tanerim/TS_TextLab/master/version.txt":
            self.settings.remove("update_url")
        self.trn = Translator(self.settings.value("language", None, str))
        self.tokenizer_service = TokenizerService()
        self.postagger_service = PosTaggerService()
        self.thread_pool = QThreadPool.globalInstance()
        self._workers: list[QRunnable] = []
        self._version_worker = None
        self._version_manual = False
        self._updates_enabled = enable_update_checks
        self.version_pool = QThreadPool(self)
        self.version_pool.setMaxThreadCount(1)
        self.version_timer = QTimer(self)
        self.version_timer.setSingleShot(True)
        self.version_timer.timeout.connect(lambda: self._start_version_check(manual=False))
        self.current_copy_text = ""
        self.current_headers: list[str] = []
        self.current_kind: TaskKind | None = None
        self.current_raw_result: TaskResult | None = None
        self.current_document: AnalysisDocument | None = None
        self.current_document_text = ""
        self.current_tokenizer_mode: TokenizerMode | None = None
        self.current_postagger_output_mode: PostaggerOutputMode | None = None
        self.current_frequency_case_mode: FrequencyCaseMode | None = None
        self.current_elapsed_ms: int | None = None
        self.concordance_source_result: TaskResult | None = None
        self._task_started_at = 0.0
        self._busy = False
        self._enforcing_splitter = False
        self._palette = palette_for("light", "indigo")
        self.logo_pixmap = QPixmap(str(resolve_resource("app", "theme", "TS_Corpus_Logo.png")))

        self.setWindowTitle(APP_NAME)
        self.setWindowIcon(QIcon(str(resolve_resource("app", "theme", "app-icon.png"))))
        self.setMinimumSize(980, 640)
        self.resize(1280, 800)
        self._build_ui()
        self._apply_theme()
        self._restore_settings()
        self._apply_translations()
        QTimer.singleShot(0, self._initialize_splitter)
        if enable_update_checks and self.settings.value("update_url", VERSION_CHECK_URL, str):
            self.version_timer.start(3000)

    def _build_ui(self) -> None:
        root = QWidget(self)
        root.setObjectName("Workspace")
        page = QVBoxLayout(root)
        page.setContentsMargins(0, 0, 0, 0)
        page.setSpacing(0)
        self.app_header = self._build_header()
        page.addWidget(self.app_header)

        body = QWidget()
        body.setObjectName("AppBody")
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(24, 18, 24, 24)
        body_layout.setSpacing(18)

        self.navigation = QFrame()
        self.navigation.setObjectName("Navigation")
        navigation_layout = QVBoxLayout(self.navigation)
        navigation_layout.setContentsMargins(12, 6, 12, 6)
        self.action_tabs = QTabBar()
        self.action_tabs.setObjectName("ActionTabs")
        self.action_tabs.setExpanding(True)
        self.action_tabs.setUsesScrollButtons(True)
        for title in ("Tokenize", "POS Tag", "Frequency", "N-grams", "Text Analysis"):
            self.action_tabs.addTab(title)
        self.action_tabs.setIconSize(QSize(18, 18))
        for index, kind in enumerate(("tokenize", "pos", "frequency", "ngrams", "dashboard")):
            self.action_tabs.setTabIcon(index, QIcon(str(resolve_resource("app", "theme", f"tool-{kind}.svg"))))
        navigation_layout.addWidget(self.action_tabs)
        body_layout.addWidget(self.navigation)

        self.action_options_stack = QStackedWidget()
        self.action_options_stack.setObjectName("ActionOptionsStack")
        self.action_options_stack.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        for builder in (self._build_tokenize_actions, self._build_pos_actions,
                        self._build_frequency_actions, self._build_ngram_actions,
                        self._build_text_analysis_actions):
            self.action_options_stack.addWidget(builder())
        body_layout.addWidget(self.action_options_stack)

        self.splitter = QSplitter(Qt.Horizontal)
        self.splitter.setChildrenCollapsible(False)
        self.splitter.setHandleWidth(18)
        self.splitter.addWidget(self._build_input_panel())
        self.splitter.addWidget(self._build_results_panel())
        self.splitter.setStretchFactor(0, 1)
        self.splitter.setStretchFactor(1, 1)
        self.splitter.splitterMoved.connect(self._enforce_splitter_limit)
        body_layout.addWidget(self.splitter, 1)
        page.addWidget(body, 1)
        self.setCentralWidget(root)

        self._connect_actions()

    def _logo_label(self, width: int, height: int, object_name: str) -> QLabel:
        label = QLabel()
        label.setObjectName(object_name)
        label.setAlignment(Qt.AlignCenter)
        label.setFixedSize(width, height)
        if not self.logo_pixmap.isNull():
            label.setPixmap(self.logo_pixmap.scaled(width, height, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        return label

    def _build_header(self) -> QWidget:
        header = QFrame()
        header.setObjectName("AppHeader")
        header.setFixedHeight(82)
        layout = QHBoxLayout(header)
        layout.setContentsMargins(28, 14, 28, 14)
        layout.setSpacing(18)

        side_width = 112
        left_side = QWidget()
        left_side.setObjectName("HeaderSide")
        left_side.setFixedWidth(side_width)
        left_layout = QHBoxLayout(left_side)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.addWidget(self._logo_label(104, 38, "HeaderLogo"))
        left_layout.addStretch(1)

        self.title_label = QLabel(APP_NAME)
        self.title_label.setObjectName("TitleLabel")
        self.title_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.subtitle_label = QLabel("Turkish Text Analysis")
        self.subtitle_label.setObjectName("SubtitleLabel")
        title_layout = QVBoxLayout()
        title_layout.setSpacing(2)
        title_layout.addWidget(self.title_label)
        title_layout.addWidget(self.subtitle_label)
        self.active_function_label = QLabel()
        self.active_function_label.setObjectName("ActiveFunction")

        right_side = QWidget()
        right_side.setObjectName("HeaderSide")
        right_side.setFixedWidth(side_width)
        right_layout = QHBoxLayout(right_side)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.addStretch(1)
        right_layout.addWidget(self._build_app_menu_button())

        layout.addWidget(left_side)
        layout.addLayout(title_layout, 1)
        layout.addWidget(self.active_function_label)
        layout.addWidget(right_side)
        return header

    def _build_app_menu_button(self) -> QToolButton:
        self.app_menu_button = QToolButton()
        self.app_menu_button.setIcon(QIcon(str(resolve_resource("app", "theme", "tool-menu.svg"))))
        self.app_menu_button.setObjectName("HeaderMenuButton")
        self.app_menu_button.setProperty("hideMenuIndicator", True)
        self.app_menu_button.setPopupMode(QToolButton.InstantPopup)
        menu = QMenu(self.app_menu_button)
        self.settings_action = menu.addAction("Settings")
        menu.addSeparator()
        self.help_action = menu.addAction("Help")
        self.about_action = menu.addAction("About TS TextLab")
        menu.addSeparator()
        self.check_version_action = menu.addAction("Check Version")
        self.settings_action.triggered.connect(self._show_settings)
        self.help_action.triggered.connect(self._show_guide)
        self.about_action.triggered.connect(self._show_about)
        self.check_version_action.triggered.connect(lambda: self._start_version_check(manual=True))
        self.app_menu_button.setMenu(menu)
        return self.app_menu_button

    def _build_input_panel(self) -> QWidget:
        panel = QFrame()
        panel.setObjectName("InputPanel")
        self.input_panel = panel
        panel.setMinimumHeight(150)
        panel.setMinimumWidth(360)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(20, 18, 20, 16)
        layout.setSpacing(12)

        top = QHBoxLayout()
        self.input_title = QLabel("INPUT")
        self.input_title.setObjectName("SectionTitle")
        self.input_meta = QLabel("0 characters · 0 spaces")
        self.input_meta.setObjectName("CounterLabel")
        top.addWidget(self.input_title)
        top.addStretch(1)
        top.addWidget(self.input_meta)
        layout.addLayout(top)

        self.input_hint = QLabel()
        self.input_hint.setObjectName("HintLabel")
        self.input_hint.setWordWrap(True)
        layout.addWidget(self.input_hint)

        self.input_text = WatermarkedPlainTextEdit(self.logo_pixmap)
        self.input_text.setObjectName("InputEditor")
        self.input_text.setFrameShape(QFrame.NoFrame)
        self.input_text.setPlaceholderText(self.trn.text("input_placeholder"))
        self.input_text.setPlainText(DEFAULT_SAMPLE_TEXT)
        self.input_title.setBuddy(self.input_text)
        self.input_text.setMinimumHeight(82)
        layout.addWidget(self.input_text, 1)

        utility_row = QHBoxLayout()
        self.open_button = QPushButton()
        self.open_button.setObjectName("SecondaryButton")
        self.open_button.clicked.connect(self._open_text_file)
        utility_row.addWidget(self.open_button)
        self.local_label = QLabel()
        self.local_label.setObjectName("LocalBadge")
        utility_row.addWidget(self.local_label)
        utility_row.addStretch(1)
        self.clear_button = QToolButton()
        self.clear_button.setText("Clear")
        self.clear_button.setObjectName("SecondaryButton")
        self.clear_button.setProperty("hideMenuIndicator", True)
        self.clear_button.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.clear_button.setPopupMode(QToolButton.InstantPopup)
        clear_menu = QMenu(self.clear_button)
        self.clear_input_action = clear_menu.addAction("Clear Input")
        self.clear_result_action = clear_menu.addAction("Clear Results")
        self.clear_all_action = clear_menu.addAction("Clear All")
        self.clear_button.setMenu(clear_menu)
        utility_row.addWidget(self.clear_button)
        layout.addLayout(utility_row)
        return panel

    def _build_results_panel(self) -> QWidget:
        panel = QFrame()
        panel.setObjectName("ResultsPanel")
        self.results_panel = panel
        panel.setMinimumHeight(280)
        panel.setMinimumWidth(420)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(18, 14, 18, 14)
        layout.setSpacing(8)

        top = QVBoxLayout()
        top.setSpacing(4)
        self.results_title = QLabel("RESULTS")
        self.results_title.setObjectName("ResultsTitle")
        self.results_title.setAlignment(Qt.AlignLeft)
        self.results_meta = QLabel("Ready")
        self.results_meta.setObjectName("ResultsSubtitle")
        self.results_meta.setAlignment(Qt.AlignLeft)
        self.results_meta.setWordWrap(True)
        top.addWidget(self.results_title)
        top.addWidget(self.results_meta)
        layout.addLayout(top)

        self.result_info = QFrame()
        self.result_info.setObjectName("ResultInfo")
        info_layout = QVBoxLayout(self.result_info)
        info_layout.setContentsMargins(12, 10, 12, 10)
        info_layout.setSpacing(8)
        self.analysis_summary_label = QLabel()
        self.analysis_summary_label.setObjectName("AnalysisSummary")
        self.analysis_summary_label.setWordWrap(True)
        info_layout.addWidget(self.analysis_summary_label)
        self.tagged_note_label = QLabel()
        self.tagged_note_label.setObjectName("TaggedNote")
        self.tagged_note_label.setWordWrap(True)
        info_layout.addWidget(self.tagged_note_label)
        self.tagged_note_label.hide()
        self.analysis_progress = QProgressBar()
        self.analysis_progress.setObjectName("AnalysisProgress")
        self.analysis_progress.setRange(0, 0)
        self.analysis_progress.setTextVisible(False)
        self.analysis_progress.setFixedHeight(6)
        info_layout.addWidget(self.analysis_progress)
        self.analysis_progress.hide()
        layout.addWidget(self.result_info)
        self.result_info.hide()

        self.concordance_context_panel = QFrame()
        self.concordance_context_panel.setObjectName("InspectorPanel")
        concordance_layout = QHBoxLayout(self.concordance_context_panel)
        concordance_layout.setContentsMargins(12, 10, 12, 10)
        concordance_layout.setSpacing(8)
        self.concordance_context_label = QLabel("Concordance")
        self.concordance_context_label.setObjectName("SectionTitle")
        self.concordance_back_button = QPushButton("Back")
        self.concordance_back_button.setObjectName("SecondaryButton")
        self.concordance_query_input = QLineEdit()
        self.concordance_span_combo = QComboBox()
        for span in (3, 5, 7, 10):
            self.concordance_span_combo.addItem(f"+/-{span}", span)
        self.concordance_context_button = QPushButton("Concordance")
        self.concordance_context_button.setObjectName("PrimaryButton")
        concordance_layout.addWidget(self.concordance_context_label)
        concordance_layout.addWidget(self.concordance_back_button)
        concordance_layout.addWidget(self.concordance_query_input, 1)
        concordance_layout.addWidget(self.concordance_span_combo)
        concordance_layout.addWidget(self.concordance_context_button)
        layout.addWidget(self.concordance_context_panel)
        self.concordance_context_panel.setVisible(False)

        filter_row = QHBoxLayout()
        filter_row.setSpacing(8)
        self.filter_input = QLineEdit()
        self.filter_input.setPlaceholderText("Filter results...")
        self.filter_input.setClearButtonEnabled(True)
        self.filter_input.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        filter_row.addWidget(self.filter_input, 1)
        layout.addLayout(filter_row)

        self.result_model = ResultTableModel(self)
        self.proxy_model = ResultProxyModel(self)
        self.proxy_model.setSourceModel(self.result_model)
        self.proxy_model.setFilterCaseSensitivity(Qt.CaseInsensitive)
        self.proxy_model.setSortRole(Qt.UserRole)

        self.table_stack = QStackedWidget()
        self.table_stack.setProperty("analysisKind", "tokenize")
        self.empty_state = EmptyState()
        self.results_table = QTableView()
        self.results_table.setFrameShape(QFrame.NoFrame)
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
        self.dashboard_view = AnalysisDashboard()
        self.dashboard_scroll = QScrollArea()
        self.dashboard_scroll.setObjectName("DashboardScroll")
        self.dashboard_scroll.setProperty("analysisKind", "dashboard")
        self.dashboard_scroll.setFrameShape(QFrame.NoFrame)
        self.dashboard_scroll.setWidgetResizable(True)
        self.dashboard_scroll.setWidget(self.dashboard_view)
        self.table_stack.addWidget(self.dashboard_scroll)
        layout.addWidget(self.table_stack, 1)

        self.status_label = QLabel("Ready")
        self.status_label.setObjectName("StatusLabel")
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

        result_actions = QHBoxLayout()
        result_actions.setSpacing(10)
        result_actions.addStretch(1)
        self.copy_button = QToolButton()
        self.copy_button.setText("Copy")
        self.copy_button.setToolTip("Copy result")
        self.copy_button.setObjectName("SecondaryButton")
        self.copy_button.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        result_actions.addWidget(self.copy_button)
        self.export_csv_button = QToolButton()
        self.export_csv_button.setText("Export CSV")
        self.export_csv_button.setToolTip("Export tab-delimited CSV")
        self.export_csv_button.setObjectName("SecondaryButton")
        self.export_csv_button.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        result_actions.addWidget(self.export_csv_button)
        layout.addLayout(result_actions)
        self._set_analysis_theme("tokenize")
        return panel

    def _build_tokenize_actions(self) -> QWidget:
        panel = QFrame()
        panel.setObjectName("ActionOptions")
        panel.setProperty("analysisKind", "tokenize")
        layout = QHBoxLayout(panel)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(10)
        self.tokenization_mode_label = QLabel("Tokenization Mode")
        self.tokenization_mode_label.setObjectName("OptionLabel")
        self.tokenizer_mode_combo = QComboBox()
        self.tokenizer_mode_combo.addItem("Tokenized", "tokenized")
        self.tokenizer_mode_combo.addItem("Tagged", "tagged")
        self.tokenizer_mode_combo.addItem("Lines", "lines")
        self.tokenize_button = QPushButton("Tokenize")
        self.tokenize_button.setObjectName("PrimaryButton")
        self.tokenize_button.setProperty("analysisKind", "tokenize")
        layout.addWidget(self.tokenization_mode_label)
        layout.addWidget(self.tokenizer_mode_combo, 1)
        layout.addWidget(self.tokenize_button)
        return panel

    def _build_pos_actions(self) -> QWidget:
        panel = QFrame()
        panel.setObjectName("ActionOptions")
        panel.setProperty("analysisKind", "pos")
        layout = QHBoxLayout(panel)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(10)
        self.postagger_output_mode_label = QLabel("POSTag Output")
        self.postagger_output_mode_label.setObjectName("OptionLabel")
        self.postagger_output_mode_combo = QComboBox()
        self.postagger_output_mode_combo.addItem("POSTag - Full (Default)", "full")
        self.postagger_output_mode_combo.addItem("POSTag - Tag", "tag")
        self.pos_button = QPushButton("POS Tag")
        self.pos_button.setObjectName("PrimaryButton")
        self.pos_button.setProperty("analysisKind", "pos")
        layout.addWidget(self.postagger_output_mode_label)
        layout.addWidget(self.postagger_output_mode_combo, 1)
        layout.addWidget(self.pos_button)
        return panel

    def _build_frequency_actions(self) -> QWidget:
        panel = QFrame()
        panel.setObjectName("ActionOptions")
        panel.setProperty("analysisKind", "frequency")
        layout = QHBoxLayout(panel)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(10)
        self.frequency_case_label = QLabel("Frequency Case")
        self.frequency_case_label.setObjectName("OptionLabel")
        self.frequency_case_combo = QComboBox()
        self.frequency_case_combo.addItem("Case-insensitive", "insensitive")
        self.frequency_case_combo.addItem("Case-sensitive", "sensitive")
        self.frequency_button = QPushButton("Frequency")
        self.frequency_button.setObjectName("PrimaryButton")
        self.frequency_button.setProperty("analysisKind", "frequency")
        layout.addWidget(self.frequency_case_label)
        layout.addWidget(self.frequency_case_combo, 1)
        layout.addWidget(self.frequency_button)
        return panel

    def _build_ngram_actions(self) -> QWidget:
        panel = QFrame()
        panel.setObjectName("ActionOptions")
        panel.setProperty("analysisKind", "ngrams")
        layout = QHBoxLayout(panel)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(10)
        filters_widget = QWidget()
        filters = QHBoxLayout(filters_widget)
        filters.setContentsMargins(0, 0, 0, 0)
        filters.setSpacing(10)
        self.ngram_n_label = QLabel("n")
        self.ngram_n_label.setObjectName("OptionLabel")
        self.ngram_n_combo = QComboBox()
        self.ngram_n_combo.setFixedWidth(84)
        for n in (2, 3, 4, 5):
            self.ngram_n_combo.addItem(str(n), n)
        self.ngram_words_check = QCheckBox("Words")
        self.ngram_punctuation_check = QCheckBox("Punctuation")
        self.ngram_urls_check = QCheckBox("URLs")
        self.ngram_mentions_check = QCheckBox("Mentions")
        self.ngram_hashtags_check = QCheckBox("Hashtags")
        self.ngram_xml_tags_check = QCheckBox("XML_Tag")
        self.ngram_words_check.setChecked(True)
        self.ngrams_button = QPushButton("N-grams")
        self.ngrams_button.setObjectName("PrimaryButton")
        self.ngrams_button.setProperty("analysisKind", "ngrams")
        layout.addWidget(self.ngram_n_label)
        layout.addWidget(self.ngram_n_combo)
        for checkbox in (
            self.ngram_words_check,
            self.ngram_punctuation_check,
            self.ngram_urls_check,
            self.ngram_mentions_check,
            self.ngram_hashtags_check,
            self.ngram_xml_tags_check,
        ):
            filters.addWidget(checkbox)
        filters.addStretch(1)
        self.ngram_filters_scroll = QScrollArea()
        self.ngram_filters_scroll.setObjectName("NgramFilters")
        self.ngram_filters_scroll.setFrameShape(QFrame.NoFrame)
        self.ngram_filters_scroll.setWidgetResizable(True)
        self.ngram_filters_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.ngram_filters_scroll.setFixedHeight(48)
        self.ngram_filters_scroll.setMinimumWidth(120)
        self.ngram_filters_scroll.setWidget(filters_widget)
        layout.addWidget(self.ngram_filters_scroll, 1)
        layout.addWidget(self.ngrams_button)
        return panel

    def _build_text_analysis_actions(self) -> QWidget:
        panel = QFrame()
        panel.setObjectName("ActionOptions")
        panel.setProperty("analysisKind", "dashboard")
        layout = QHBoxLayout(panel)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.addStretch(1)
        return panel

    def _connect_actions(self) -> None:
        self.tokenize_button.clicked.connect(lambda: self._start_task("tokenize"))
        self.pos_button.clicked.connect(lambda: self._start_task("pos"))
        self.frequency_button.clicked.connect(lambda: self._start_task("frequency"))
        self.ngrams_button.clicked.connect(lambda: self._start_task("ngrams"))
        self.concordance_context_button.clicked.connect(self._start_concordance_from_input)
        self.concordance_query_input.returnPressed.connect(self._start_concordance_from_input)
        self.concordance_back_button.clicked.connect(self._restore_concordance_source)
        self.copy_button.clicked.connect(self._copy_result)
        self.export_csv_button.clicked.connect(self._export_result_csv)
        self.clear_input_action.triggered.connect(self.input_text.clear)
        self.clear_result_action.triggered.connect(self._clear_result)
        self.clear_all_action.triggered.connect(self._clear_all)
        self._input_meta_timer = QTimer(self)
        self._input_meta_timer.setSingleShot(True)
        self._input_meta_timer.setInterval(200)
        self._input_meta_timer.timeout.connect(self._update_input_meta)
        self.input_text.textChanged.connect(lambda: self._input_meta_timer.start())
        self.tokenizer_mode_combo.currentIndexChanged.connect(self._save_tokenizer_mode)
        self.postagger_output_mode_combo.currentIndexChanged.connect(self._save_postagger_output_mode)
        self.frequency_case_combo.currentIndexChanged.connect(self._save_frequency_case_mode)
        self.filter_input.textChanged.connect(self._filter_results)
        self.results_table.clicked.connect(self._inspect_clicked_row)
        self.action_tabs.currentChanged.connect(self._sync_action_options)

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
        self._set_analysis_theme(self._kind_for_tab(self.action_tabs.currentIndex()))
        self._apply_delegates()
        if self.current_raw_result is not None and self.current_kind == "dashboard":
            self.dashboard_view.set_result(self.current_raw_result, self.trn, self._palette)

    def _apply_density(self) -> None:
        density = self.settings.value("table_density", "comfortable", str)
        self.results_table.verticalHeader().setDefaultSectionSize(32 if density == "compact" else 42)

    def _apply_delegates(self) -> None:
        self.results_table.setItemDelegate(QStyledItemDelegate(self.results_table))
        for column in range(max(4, self.result_model.columnCount())):
            self.results_table.setItemDelegateForColumn(column, None)
        if self.current_kind == "pos":
            pos_column = len(self.result_model.headers)
            self.results_table.setItemDelegateForColumn(
                pos_column, PosBadgeDelegate(self._palette, pos_column, self.results_table)
            )
        elif self.current_kind in {"frequency", "ngrams"}:
            self.results_table.setItemDelegateForColumn(2, FrequencyBarDelegate(self._palette, 2, self.results_table))

    def _restore_settings(self) -> None:
        if self.settings.value("remember_layout", True, bool):
            geometry = self.settings.value("window_geometry")
            if geometry:
                self.restoreGeometry(geometry)
        mode = self.settings.value("tokenizer_mode", self.settings.value("default_tokenizer_mode", "tokenized", str), str)
        if mode == "tagged_lines":
            mode = "tagged"
        _set_combo_data(self.tokenizer_mode_combo, mode)
        _set_combo_data(self.postagger_output_mode_combo, self.settings.value("postagger_output_mode", "full", str))
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
        self.version_timer.stop()
        if self.settings.value("remember_layout", True, bool):
            self.settings.setValue("window_geometry", self.saveGeometry())
            self.settings.setValue("splitter_sizes_horizontal", self.splitter.sizes())
        super().closeEvent(event)

    def _theme_setting(self) -> ThemeName:
        return "light"

    def _open_text_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, self.trn.text("open"), "", "Text files (*.txt)")
        if not path:
            return
        from pathlib import Path
        try:
            data = Path(path).read_bytes()
            text = data.decode("utf-16") if data.startswith((b"\xff\xfe", b"\xfe\xff")) else data.decode("utf-8-sig")
        except (OSError, UnicodeError) as exc:
            QMessageBox.warning(self, self.trn.text("error"), self.trn.text("open_error", error=str(exc)))
            return
        limit = self.settings.value("max_input_units", DEFAULT_MAX_INPUT_UNITS, int)
        if text.count(" ") > limit:
            QMessageBox.warning(self, self.trn.text("error"), self.trn.text("input_limit", limit=f"{limit:,}", count=f"{text.count(' '):,}"))
            return
        self.input_text.setPlainText(text)

    def _start_task(self, kind: TaskKind) -> None:
        if self._busy:
            return
        text = self.input_text.toPlainText()
        limit = self.settings.value("max_input_units", DEFAULT_MAX_INPUT_UNITS, int)
        if text.count(" ") > limit:
            QMessageBox.warning(self, self.trn.text("error"), self.trn.text("input_limit", limit=f"{limit:,}", count=f"{text.count(' '):,}"))
            return
        self._task_started_at = time.perf_counter()
        self._set_busy(True, kind)
        self._set_status(self.trn.text("preparing_pos") if kind == "pos" else self.trn.text("processing"))
        worker = NlpWorker(
            kind,
            text,
            self.tokenizer_mode_combo.currentData(),
            self.postagger_output_mode_combo.currentData(),
            self.frequency_case_combo.currentData(),
            self.ngram_n_combo.currentData(),
            self._selected_ngram_types(),
            self.concordance_query_input.text(),
            self.concordance_span_combo.currentData(),
            self.current_document if text == self.current_document_text else None,
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
        self.current_raw_result = result
        result = self._localized_result(result)
        self.current_copy_text = result.copy_text
        self.current_headers = result.headers
        self.current_kind = result.kind
        if result.document is not None:
            self.current_document = result.document
            self.current_document_text = self.input_text.toPlainText()
        self.current_tokenizer_mode = result.tokenizer_mode
        self.current_postagger_output_mode = result.postagger_output_mode
        self.current_frequency_case_mode = result.frequency_case_mode
        self.current_elapsed_ms = elapsed_ms
        if result.kind == "frequency":
            self.concordance_source_result = self.current_raw_result
        self._select_action_tab_for_kind(result.kind)
        self._set_analysis_theme(self._kind_for_tab(self.action_tabs.currentIndex()))
        self.action_options_stack.setVisible(result.kind != "dashboard")
        self.concordance_back_button.setVisible(result.kind == "concordance")
        if result.kind not in {"frequency", "concordance"}:
            self.concordance_context_panel.setVisible(False)
        elif result.kind == "frequency":
            self.concordance_context_panel.setVisible(True)
        # Reset the previous sort before replacing rows: token/POS/KWIC outputs
        # already have source order, and frequency results are sorted by the worker.
        self.results_table.setSortingEnabled(False)
        self.proxy_model.sort(-1)
        self.result_model.set_result(result)
        self.proxy_model.invalidateFilter()
        self.filter_input.setVisible(result.kind != "dashboard")
        self.export_csv_button.setVisible(True)
        if result.kind == "dashboard":
            dashboard_source = self.current_raw_result or result
            self.dashboard_view.set_result(dashboard_source, self.trn, self._palette)
            self.table_stack.setCurrentWidget(self.dashboard_scroll)
            self.results_table.setSortingEnabled(False)
        else:
            self.table_stack.setCurrentWidget(self.results_table)
            self.results_table.setSortingEnabled(result.kind in {"frequency", "ngrams"})
            header = self.results_table.horizontalHeader()
            header.setStretchLastSection(False)
            header.setMinimumSectionSize(44)
            header.setSectionResizeMode(QHeaderView.Stretch)
            header.setSectionResizeMode(0, QHeaderView.Fixed)
            self.results_table.setColumnWidth(0, 48)
            if result.kind == "pos":
                pos_column = len(result.headers)
                header.setSectionResizeMode(pos_column, QHeaderView.Fixed)
                self.results_table.setColumnWidth(pos_column, 104)
            elif result.kind in {"frequency", "ngrams"}:
                header.setSectionResizeMode(2, QHeaderView.Fixed)
                self.results_table.setColumnWidth(2, 116)
            elif result.kind == "concordance":
                header.setSectionResizeMode(2, QHeaderView.Fixed)
                self.results_table.setColumnWidth(2, 160)
            if result.kind in {"frequency", "ngrams"}:
                self.results_table.sortByColumn(2, Qt.DescendingOrder)
            else:
                self.proxy_model.sort(-1)
        self._apply_delegates()

        label = self._kind_label(result)
        count_label = self._count_label(result.kind, len(result.rows))
        self.results_meta.setText(self._results_meta_text(label, count_label, result.kind))
        self._set_status("")
        self._update_result_info()
        self._set_busy(False)

    @Slot(str)
    def _display_error(self, message: str) -> None:
        self._set_status(message)
        self.results_meta.setText(f"{self.trn.text('analysis')} · {self.trn.text('error')}")
        self._set_busy(False)
        self.result_info.show()
        self.analysis_summary_label.setText(message)
        self.tagged_note_label.hide()

    @Slot(object)
    def _display_version_result(self, result: VersionCheckResult) -> None:
        manual = self._version_manual
        self.check_version_action.setEnabled(True)
        self.check_version_action.setText(self.trn.text("check_version"))
        self._version_worker = None
        if self._updates_enabled and self.settings.value("update_url", VERSION_CHECK_URL, str):
            self.version_timer.start(VERSION_CHECK_INTERVAL_MS if result.checked else VERSION_CHECK_RETRY_MS)
        if result.checked:
            self.settings.setValue("last_update_check", datetime.now().astimezone().isoformat())
            self.settings.setValue("latest_version", result.latest_version)
        if result.update_available:
            if manual or self.settings.value("notified_version", "", str) != result.latest_version:
                self.settings.setValue("notified_version", result.latest_version)
                NoticeDialog(self.trn, self.trn.text("update_title"),
                    self.trn.text("update_body", latest=result.latest_version, current=APP_VERSION), self,
                    download_url=result.download_url).exec()
        elif manual:
            NoticeDialog(self.trn, self.trn.text("updates"),
                self.trn.text("up_to_date") if result.checked else self.trn.text("version_check_failed"),
                self, detail=APP_VERSION if result.checked else self.trn.text("update_failure_hint")).exec()

    def _set_status(self, text: str) -> None:
        self.status_label.setText(text)
        self.status_label.setVisible(bool(text))

    def _copy_result(self) -> None:
        self._copy_selection_or_result()

    def _export_result_csv(self) -> None:
        result = self.current_raw_result
        if self.current_kind is None or result is None:
            self._set_status(self.trn.text("no_export_result"))
            return
        timestamp = datetime.now().astimezone().strftime("%Y%m%d-%H%M%S-%f")
        default_name = f"ts-textlab-{self._export_kind_name()}-{timestamp}.csv"
        path, _ = QFileDialog.getSaveFileName(
            self,
            self.trn.text("export_csv"),
            default_name,
            self.trn.text("csv_file_filter"),
        )
        if not path:
            return
        target = timestamped_csv_path(path, timestamp)
        try:
            # Export the complete result with stable source headers, independent of UI language.
            write_tab_csv(target, result.headers, result.rows)
        except (OSError, ValueError) as exc:
            logger.exception("CSV export failed")
            self._set_status(f"{self.trn.text('operation_failed')}: {exc}")
            return
        self._set_status(self.trn.text("csv_exported", filename=target.name))

    def _export_kind_name(self) -> str:
        return {
            "tokenize": "tokenize",
            "pos": "postag",
            "frequency": "frequency",
            "ngrams": "ngrams",
            "concordance": "concordance",
            "dashboard": "dashboard",
        }.get(self.current_kind or "", "results")

    def _copy_selection_or_result(self) -> None:
        selected_text = self._selected_rows_text()
        text = selected_text or self.current_copy_text
        if not text:
            self._set_status(self.trn.text("no_result"))
            return
        QGuiApplication.clipboard().setText(text)
        self._set_status(self.trn.text("selection_copied") if selected_text else self.trn.text("copied"))

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
        self._reset_result_display(self.trn.text("cleared"))

    def _reset_result_display(self, status_text: str | None = None) -> None:
        self.current_copy_text = ""
        self.current_headers = []
        self.current_kind = None
        self.current_raw_result = None
        self.current_tokenizer_mode = None
        self.current_postagger_output_mode = None
        self.current_frequency_case_mode = None
        self.current_elapsed_ms = None
        self.concordance_source_result = None
        self.result_model.set_result(None)
        self.filter_input.clear()
        self.filter_input.setVisible(True)
        self.export_csv_button.setVisible(True)
        self.dashboard_view.set_result(None, self.trn, self._palette)
        self.table_stack.setCurrentWidget(self.empty_state)
        self.concordance_context_panel.setVisible(False)
        self.results_meta.setText(self.trn.text("ready"))
        self._set_status(status_text or self.trn.text("ready"))
        self.result_info.hide()
        self.tagged_note_label.hide()

    def _clear_all(self) -> None:
        self.current_document = None
        self.current_document_text = ""
        self.postagger_service._cached_text = None
        self.postagger_service._cached_tokens = None
        self.input_text.clear()
        self._clear_result()

    def _set_busy(self, busy: bool, kind: TaskKind | None = None) -> None:
        self._busy = busy
        for button in (
            self.tokenize_button,
            self.pos_button,
            self.frequency_button,
            self.ngrams_button,
            self.concordance_context_button,
            self.concordance_back_button,
        ):
            button.setDisabled(busy)
        self.input_text.setReadOnly(busy)
        self.open_button.setDisabled(busy)
        self.clear_button.setDisabled(busy)
        self.copy_button.setDisabled(busy)
        self.export_csv_button.setDisabled(busy)
        self.postagger_output_mode_combo.setDisabled(busy)
        self.action_tabs.setEnabled(not busy)
        self.action_options_stack.setEnabled(not busy)
        self.analysis_progress.setVisible(busy)
        if busy:
            text = self.trn.text("preparing_pos") if kind == "pos" else self.trn.text("processing")
            self.results_meta.setText(f"{self.trn.text('analysis')} · {text}")
            self.result_info.show()
            self.analysis_summary_label.setText(text)
            self.tagged_note_label.hide()
            QApplication.setOverrideCursor(Qt.WaitCursor)
        else:
            QApplication.restoreOverrideCursor()

    def _apply_translations(self) -> None:
        self.open_button.setText(self.trn.text("open"))
        self.input_text.setPlaceholderText(self.trn.text("input_placeholder"))
        self.input_hint.setText(self.trn.text("input_hint"))
        self.local_label.setText(self.trn.text("local_badge"))
        self._update_active_function()
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
        self.postagger_output_mode_label.setText(self.trn.text("postagger_output"))
        self.postagger_output_mode_combo.setItemText(0, self.trn.text("postagger_full_default"))
        self.postagger_output_mode_combo.setItemText(1, self.trn.text("postagger_tag"))
        self.tokenize_button.setText(self.trn.text("tokenize"))
        self.pos_button.setText(self.trn.text("pos_tag"))
        self.frequency_button.setText(self.trn.text("frequency"))
        self.ngrams_button.setText(self.trn.text("ngrams"))
        self.concordance_context_label.setText(self.trn.text("concordance"))
        self.concordance_context_button.setText(self.trn.text("concordance"))
        self.concordance_back_button.setText(self.trn.text("back"))
        self.export_csv_button.setText(self.trn.text("export_csv"))
        self.export_csv_button.setToolTip(self.trn.text("csv_file_filter"))
        self.action_tabs.setTabText(0, self.trn.text("tokenize"))
        self.action_tabs.setTabText(1, self.trn.text("pos_tag"))
        self.action_tabs.setTabText(2, self.trn.text("frequency"))
        self.action_tabs.setTabText(3, self.trn.text("ngrams"))
        self.action_tabs.setTabText(4, self.trn.text("text_analysis"))
        self.clear_button.setText(self.trn.text("clear"))
        self.clear_input_action.setText(self.trn.text("clear_input"))
        self.clear_result_action.setText(self.trn.text("clear_result"))
        self.clear_all_action.setText(self.trn.text("clear_all"))
        self.copy_button.setText(self.trn.text("copy"))
        self.copy_button.setToolTip(self.trn.text("copy_result"))
        self.ngram_words_check.setText(self.trn.text("words"))
        self.ngram_punctuation_check.setText(self.trn.text("punctuation"))
        self.ngram_urls_check.setText(self.trn.text("urls"))
        self.ngram_mentions_check.setText(self.trn.text("mentions"))
        self.ngram_hashtags_check.setText(self.trn.text("hashtags"))
        self.ngram_xml_tags_check.setText(self.trn.text("xml_tags"))
        self.concordance_query_input.setPlaceholderText(self.trn.text("token"))
        self.filter_input.setPlaceholderText(self.trn.text("filter_results"))
        self.input_text.setAccessibleName(self.trn.text("input"))
        self.filter_input.setAccessibleName(self.trn.text("filter_results"))
        self.action_tabs.setAccessibleName(self.trn.text("actions"))
        self.app_menu_button.setToolTip(self.trn.text("application_menu"))
        self.settings_action.setText(self.trn.text("settings"))
        self.help_action.setText(self.trn.text("help"))
        self.about_action.setText(f"{self.trn.text('about')} TS TextLab")
        self.check_version_action.setText(self.trn.text("check_version"))
        self.empty_state.apply_translations(self.trn)
        self._fit_action_options()
        self._update_input_meta()
        if self.current_kind is not None:
            if self.current_raw_result is not None:
                self.result_model.set_result(self._localized_result(self.current_raw_result))
                if self.current_kind == "dashboard":
                    self.dashboard_view.set_result(self.current_raw_result, self.trn, self._palette)
            else:
                self.result_model.beginResetModel()
                self.result_model.headers = self._headers_for_current_result()
                self.result_model.endResetModel()
            visible = self.proxy_model.rowCount()
            self.results_meta.setText(
                self._results_meta_text(
                    self._kind_label_from_current(),
                    self._visible_count_label(visible),
                    self.current_kind,
                )
            )
            self._set_status("")
            self._update_result_info()
        if not self.current_copy_text:
            self._set_status(self.trn.text("ready"))

    def _start_version_check(self, manual: bool = True) -> None:
        if self._version_worker is not None:
            self._version_manual = self._version_manual or manual
            return
        url = self.settings.value("update_url", VERSION_CHECK_URL, str)
        if not url:
            if manual:
                NoticeDialog(self.trn, self.trn.text("updates"), self.trn.text("update_source_missing"), self).exec()
            return
        self._version_manual = manual
        self.check_version_action.setEnabled(False)
        if manual:
            self.check_version_action.setText(self.trn.text("checking_version"))
        worker = VersionWorker(url)
        self._version_worker = worker
        worker.signals.finished.connect(self._display_version_result)
        self._workers.append(worker)
        self.version_pool.start(worker)

    def _show_settings(self) -> None:
        dialog = SettingsDialog(self.settings, self, self._apply_theme, self._apply_language)
        if dialog.exec() == QDialog.Accepted:
            self._apply_theme()
            if self._updates_enabled:
                self.version_timer.stop()
                if self.settings.value("update_url", VERSION_CHECK_URL, str):
                    self.version_timer.start(1000)
            _set_combo_data(self.tokenizer_mode_combo, self.settings.value("default_tokenizer_mode", "tokenized", str))

    def _apply_language(self) -> None:
        self.trn = Translator(self.settings.value("language", None, str))
        self._apply_translations()

    def _show_about(self) -> None:
        AboutDialog(self.trn, self.logo_pixmap, self).exec()

    def _show_guide(self) -> None:
        dialog = QDialog(self)
        dialog.setWindowTitle(self.trn.text("help"))
        dialog.setMinimumSize(760, 500)
        dialog.resize(920, 680)
        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(24, 24, 24, 0)
        layout.setSpacing(16)
        title = QLabel(self.trn.text("guide"))
        title.setObjectName("DialogTitle")
        layout.addWidget(title)
        subtitle = QLabel(self.trn.text("help_intro"))
        subtitle.setObjectName("DialogMuted")
        subtitle.setWordWrap(True)
        layout.addWidget(subtitle)

        body = QHBoxLayout()
        body.setSpacing(18)
        navigation = QListWidget()
        navigation.setObjectName("HelpNavigation")
        navigation.setFixedWidth(210)
        navigation.setAccessibleName(self.trn.text("help_topics"))
        pages = QStackedWidget()
        topics = (
            ("help_start", "help_start_body"),
            ("tokenization", "help_tokenization_body"),
            ("pos_tagging", "help_pos_body"),
            ("frequency", "help_frequency_body"),
            ("ngrams", "help_ngrams_body"),
            ("concordance", "help_concordance_body"),
            ("text_analysis", "help_analysis_body"),
            ("export_csv", "help_export_body"),
            ("settings", "help_settings_body"),
            ("keyboard_shortcuts", "help_shortcuts_body"),
        )
        modifier = "Cmd" if QGuiApplication.platformName() == "cocoa" else "Ctrl"
        for heading_key, body_key in topics:
            navigation.addItem(self.trn.text(heading_key))
            scroll = QScrollArea()
            scroll.setObjectName("HelpScroll")
            scroll.setWidgetResizable(True)
            scroll.setFrameShape(QFrame.NoFrame)
            scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
            page = QWidget()
            page.setObjectName("HelpPage")
            page_layout = QVBoxLayout(page)
            page_layout.setContentsMargins(0, 0, 8, 0)
            page_layout.setSpacing(14)
            heading = QLabel(self.trn.text(heading_key))
            heading.setObjectName("HelpHeading")
            heading.setWordWrap(True)
            page_layout.addWidget(heading)
            for paragraph in self.trn.text(body_key, modifier=modifier).split("\n\n"):
                card = QFrame()
                card.setObjectName("DialogCard")
                card_layout = QVBoxLayout(card)
                card_layout.setContentsMargins(18, 16, 18, 16)
                text = QLabel(paragraph)
                text.setObjectName("HelpBody")
                text.setWordWrap(True)
                text.setTextInteractionFlags(Qt.TextSelectableByMouse)
                card_layout.addWidget(text)
                page_layout.addWidget(card)
            page_layout.addStretch(1)
            scroll.setWidget(page)
            pages.addWidget(scroll)
        navigation.currentRowChanged.connect(pages.setCurrentIndex)
        navigation.setCurrentRow(0)
        body.addWidget(navigation)
        body.addWidget(pages, 1)
        layout.addLayout(body, 1)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok)
        buttons.button(QDialogButtonBox.Ok).setText(self.trn.text("ok"))
        _style_dialog_buttons(buttons)
        buttons.accepted.connect(dialog.accept)
        layout.addWidget(self._dialog_footer(buttons))
        dialog.exec()

    def _show_shortcuts(self) -> None:
        modifier = "Cmd" if QGuiApplication.platformName() == "cocoa" else "Ctrl"
        dialog = QDialog(self)
        dialog.setWindowTitle(self.trn.text("keyboard_shortcuts"))
        dialog.setMinimumWidth(420)
        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(22, 22, 22, 0)
        layout.setSpacing(14)

        title = QLabel(self.trn.text("keyboard_shortcuts"))
        title.setObjectName("DialogTitle")
        layout.addWidget(title)

        card = QFrame()
        card.setObjectName("DialogCard")
        grid = QGridLayout(card)
        grid.setContentsMargins(16, 14, 16, 14)
        grid.setHorizontalSpacing(18)
        grid.setVerticalSpacing(10)
        rows = [
            (f"{modifier}+Enter", self.trn.text("tokenize")),
            (f"{modifier}+Shift+P", self.trn.text("pos_tag")),
            (f"{modifier}+Shift+F", self.trn.text("frequency")),
            (f"{modifier}+C", self.trn.text("copy")),
            (f"{modifier}+L", self.trn.text("input")),
            (f"{modifier}+,", self.trn.text("settings")),
        ]
        for row, (shortcut, action) in enumerate(rows):
            shortcut_label = QLabel(shortcut)
            shortcut_label.setObjectName("KbdLabel")
            action_label = QLabel(action)
            action_label.setObjectName("DialogMuted")
            grid.addWidget(shortcut_label, row, 0)
            grid.addWidget(action_label, row, 1)
        grid.setColumnStretch(1, 1)
        layout.addWidget(card)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok)
        ok_button = buttons.button(QDialogButtonBox.Ok)
        if ok_button is not None:
            ok_button.setText(self.trn.text("ok"))
            ok_button.setObjectName("DialogPrimaryButton")
        buttons.accepted.connect(dialog.accept)
        layout.addWidget(self._dialog_footer(buttons))
        dialog.exec()

    def _dialog_card(self, title: str, body: str, rich: bool = False, align_center: bool = False) -> QFrame:
        card = QFrame()
        card.setObjectName("DialogCard")
        card.setProperty("flat", align_center)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 13, 16, 14)
        layout.setSpacing(6)
        title_label = QLabel(title)
        title_label.setObjectName("DialogSection")
        if rich:
            body = body.replace('<a ', '<a style="color:#2563EB; text-decoration:none;" ')
        body_label = QLabel(body)
        body_label.setObjectName("DialogMuted")
        body_label.setWordWrap(True)
        if align_center:
            title_label.setAlignment(Qt.AlignCenter)
            body_label.setAlignment(Qt.AlignCenter)
        if rich:
            body_label.setOpenExternalLinks(True)
            body_label.setTextFormat(Qt.RichText)
            body_label.setTextInteractionFlags(Qt.TextBrowserInteraction)
        layout.addWidget(title_label)
        layout.addWidget(body_label)
        return card

    def _dialog_footer(self, buttons: QDialogButtonBox, align_center: bool = False) -> QFrame:
        footer = QFrame()
        footer.setObjectName("DialogFooter")
        footer.setProperty("flat", align_center)
        layout = QHBoxLayout(footer)
        layout.setContentsMargins(0, 12, 0, 14)
        layout.addStretch(1)
        layout.addWidget(buttons)
        if align_center:
            layout.addStretch(1)
        return footer

    def _focus_input(self) -> None:
        self.input_text.setFocus()
        self.input_text.moveCursor(QTextCursor.End)

    def _filter_results(self, text: str) -> None:
        self.proxy_model.set_filter_text(text)
        visible = self.proxy_model.rowCount()
        if self.result_model.rowCount():
            self.results_meta.setText(
                self._results_meta_text(
                    self._kind_label_from_current(),
                    self._visible_count_label(visible),
                    self.current_kind,
                )
            )

    def _results_meta_text(self, label: str, count_label: str, kind: TaskKind | None) -> str:
        text = f"{self.trn.text('analysis')} · {label} · {count_label}"
        if kind == "frequency":
            text = f"{text} | {self.trn.text('select_token_for_concordance')}"
        return text

    def _start_concordance_from_input(self) -> None:
        if not self.concordance_query_input.text().strip():
            self._set_status(self.trn.text("no_result"))
            return
        self._start_task("concordance")

    def _restore_concordance_source(self) -> None:
        if self.concordance_source_result is None:
            self._set_status(self.trn.text("no_result"))
            return
        self._task_started_at = time.perf_counter()
        self._display_result(self.concordance_source_result)

    def _inspect_clicked_row(self, index: QModelIndex) -> None:
        source_index = self.proxy_model.mapToSource(index)
        if not source_index.isValid() or self.current_document is None:
            return
        row = source_index.row()
        if row >= len(self.result_model.rows):
            return
        values = self.result_model.rows[row]
        surface = self._surface_from_row(values)
        if not surface:
            return
        if self.current_kind == "frequency":
            self.concordance_query_input.setText(surface)
            self.concordance_context_panel.setVisible(True)

    def _surface_from_row(self, values: tuple[str, ...]) -> str:
        if not values:
            return ""
        if self.current_kind == "concordance" and len(values) >= 2:
            return values[1]
        if self.current_kind in {"tokenize", "pos", "frequency"}:
            return values[0]
        return ""

    def _update_input_meta(self) -> None:
        text = self.input_text.toPlainText()
        spaces = text.count(" ")
        self.input_meta.setText(f"{len(text):,} {self.trn.text('characters')} · {spaces:,} {self.trn.text('spaces')}")

    def _save_tokenizer_mode(self) -> None:
        self.settings.setValue("tokenizer_mode", self.tokenizer_mode_combo.currentData())

    def _save_postagger_output_mode(self) -> None:
        self.settings.setValue("postagger_output_mode", self.postagger_output_mode_combo.currentData())

    def _save_frequency_case_mode(self) -> None:
        self.settings.setValue("frequency_case_mode", self.frequency_case_combo.currentData())

    def _selected_ngram_types(self) -> set[str]:
        selected = set()
        if self.ngram_words_check.isChecked():
            selected.add("Words")
        if self.ngram_punctuation_check.isChecked():
            selected.add("Punctuation")
        if self.ngram_urls_check.isChecked():
            selected.add("URLs")
        if self.ngram_mentions_check.isChecked():
            selected.add("Mentions")
        if self.ngram_hashtags_check.isChecked():
            selected.add("Hashtags")
        if self.ngram_xml_tags_check.isChecked():
            selected.add("XML_Tag")
        return selected or {"Words"}

    def _sync_action_options(self, index: int) -> None:
        self.action_options_stack.setCurrentIndex(index)
        self._fit_action_options()
        target_kind = self._kind_for_tab(index)
        self.action_options_stack.setVisible(target_kind != "dashboard")
        self._set_analysis_theme(target_kind)
        text = self.input_text.toPlainText()
        current_tab_kind = "frequency" if self.current_kind == "concordance" else self.current_kind
        if current_tab_kind is not None and current_tab_kind != target_kind:
            self._reset_result_display()
        if target_kind == "dashboard" and text.strip() and (
            self.current_kind != "dashboard" or text != self.current_document_text
        ):
            self._start_task("dashboard")

    def _kind_for_tab(self, index: int) -> str:
        return {
            0: "tokenize",
            1: "pos",
            2: "frequency",
            3: "ngrams",
            4: "dashboard",
        }.get(index, "tokenize")

    def _fit_action_options(self) -> None:
        page = self.action_options_stack.currentWidget()
        if page is not None:
            self.action_options_stack.setFixedHeight(page.sizeHint().height() + 2)

    def _set_analysis_theme(self, kind: str) -> None:
        # The chosen tool is a workspace state, visible on both sides of the split.
        kind = "frequency" if kind == "concordance" else kind
        self._palette = palette_for("light", {
            "tokenize": "blue", "pos": "emerald", "frequency": "soft_red",
            "ngrams": "violet", "dashboard": "petrol",
        }.get(kind, "indigo"))
        for widget in (
            self.app_header,
            self.navigation,
            self.input_panel,
            self.input_text,
            self.input_title,
            self.input_meta,
            self.active_function_label,
            self.filter_input,
            self.concordance_context_button,
            self.result_info,
            self.analysis_progress,
            self.action_tabs,
            self.results_panel,
            self.action_options_stack,
            self.table_stack,
            self.dashboard_scroll,
            self.results_table,
            self.results_title,
            self.results_meta,
            self.status_label,
        ):
            widget.setProperty("analysisKind", kind)
            self._refresh_style(widget)
        self._update_active_function()

    def _update_active_function(self) -> None:
        selected = self.action_tabs.currentIndex()
        for index, kind in enumerate(("tokenize", "pos", "frequency", "ngrams", "dashboard")):
            suffix = "-selected" if index == selected else ""
            self.action_tabs.setTabIcon(index, QIcon(str(resolve_resource("app", "theme", f"tool-{kind}{suffix}.svg"))))
        key = {
            "tokenize": "tokenization", "pos": "pos_tagging", "frequency": "frequency",
            "ngrams": "ngrams", "dashboard": "text_analysis",
        }[self._kind_for_tab(self.action_tabs.currentIndex())]
        self.active_function_label.setText(self.trn.text(key))

    def _refresh_style(self, widget: QWidget) -> None:
        style = widget.style()
        style.unpolish(widget)
        style.polish(widget)
        widget.update()

    def _select_action_tab_for_kind(self, kind: TaskKind) -> None:
        tab = {
            "tokenize": 0,
            "pos": 1,
            "frequency": 2,
            "concordance": 2,
            "ngrams": 3,
            "dashboard": 4,
        }.get(kind)
        if tab is not None and self.action_tabs.currentIndex() != tab:
            self.action_tabs.setCurrentIndex(tab)

    def _localized_result(self, result: TaskResult) -> TaskResult:
        rows = result.rows
        return TaskResult(
            kind=result.kind,
            headers=[self._header_label(header) for header in result.headers],
            rows=rows,
            copy_text=result.copy_text,
            document=result.document,
            tokenizer_mode=result.tokenizer_mode,
            postagger_output_mode=result.postagger_output_mode,
            frequency_case_mode=result.frequency_case_mode,
            analysis_label_key=result.analysis_label_key,
        )

    def _localized_row(self, kind: TaskKind, row: tuple[str, ...]) -> tuple[str, ...]:
        if not row:
            return row
        return row

    def _row_label(self, value: str) -> str:
        return {
            "Characters": self.trn.text("characters_measure"),
            "Tokens": self.trn.text("tokens_measure"),
            "Lexical tokens": self.trn.text("lexical_tokens"),
            "Unique tokens": self.trn.text("unique_tokens"),
            "Sentences": self.trn.text("sentences"),
            "Punctuation": self.trn.text("punctuation"),
            "Type-token ratio": self.trn.text("type_token_ratio"),
            "Mean token length": self.trn.text("mean_token_length"),
            "Mean sentence length": self.trn.text("mean_sentence_length"),
            "Paragraph count": self.trn.text("paragraph_count"),
            "Mean paragraph length": self.trn.text("mean_paragraph_length"),
            "Median paragraph length": self.trn.text("median_paragraph_length"),
            "Shortest paragraph": self.trn.text("shortest_paragraph"),
            "Longest paragraph": self.trn.text("longest_paragraph"),
            "Sentence count": self.trn.text("sentence_count"),
            "Median sentence length": self.trn.text("median_sentence_length"),
            "Shortest sentence": self.trn.text("shortest_sentence"),
            "Longest sentence": self.trn.text("longest_sentence"),
            "Punctuation density": self.trn.text("punctuation_density"),
            "Lexical density": self.trn.text("lexical_density"),
            "Lexical Density": self.trn.text("lexical_density"),
            "Recognized lexical forms": self.trn.text("recognized_lexical_forms"),
            "Lexical Words": self.trn.text("lexical_words"),
            "Function Words": self.trn.text("function_words"),
            "POS distribution": self.trn.text("pos_distribution_info"),
            "Other Lexical Tokens": self.trn.text("other_lexical_tokens"),
            "Surface": self.trn.text("surface"),
            "Position": self.trn.text("position"),
            "Tokenizer": self.trn.text("tokenizer"),
            "Length": self.trn.text("length"),
            "Frequency": self.trn.text("count"),
            "Sentence": self.trn.text("sentence"),
            "Mention": self.trn.text("mentions"),
            "Hashtag": self.trn.text("hashtags"),
            "XML_Tag": self.trn.text("xml_tags"),
            "URL": self.trn.text("urls"),
            "Emoji": self.trn.text("emojis"),
            "Email": self.trn.text("emails"),
            "Date": self.trn.text("dates"),
            "Time": self.trn.text("times"),
        }.get(value, value)

    def _description_label(self, value: str) -> str:
        return {
            "Total Unicode code points in the input text.": self.trn.text("characters_description"),
            "All non-empty TS Tokenizer tokens.": self.trn.text("tokens_description"),
            "Word-like tokens used for lexical calculations.": self.trn.text("lexical_tokens_description"),
            "Distinct lexical forms after case folding.": self.trn.text("unique_tokens_description"),
            "Line-based units; each non-empty input line is counted as one unit.": self.trn.text("line_units_description"),
            "Tokens classified or detected as punctuation.": self.trn.text("punctuation_description"),
            "Unique lexical tokens divided by lexical tokens.": self.trn.text("ttr_description"),
            "Average character length of lexical tokens.": self.trn.text("mean_token_length_description"),
            "Average lexical tokens per non-empty line.": self.trn.text("mean_line_length_description"),
        }.get(value, value)

    def _header_label(self, header: str) -> str:
        return {
            "Token": self.trn.text("token"),
            "Lowercase": self.trn.text("lowercase"),
            "Tag": self.trn.text("tag"),
            "POS": self.trn.text("pos"),
            "Line": self.trn.text("line"),
            "Result": self.trn.text("result"),
            "Count": self.trn.text("count"),
            "Frequency": self.trn.text("count"),
            "Percentage": self.trn.text("percentage"),
            "Category": self.trn.text("category"),
            "Measure": self.trn.text("measure"),
            "Value": self.trn.text("value"),
            "Property": self.trn.text("property"),
            "Description": self.trn.text("description"),
            "Info": self.trn.text("info"),
            "Left": self.trn.text("left_context"),
            "Node": self.trn.text("node"),
            "Right": self.trn.text("right_context"),
            "N-gram": self.trn.text("ngram"),
            "Distribution": self.trn.text("distribution"),
        }.get(header, header)

    def _headers_for_current_result(self) -> list[str]:
        if self.current_kind == "frequency":
            return [self.trn.text("token"), self.trn.text("count")]
        if self.current_kind == "ngrams":
            return [self.trn.text("ngram"), self.trn.text("count")]
        if self.current_kind == "concordance":
            return [self.trn.text("left_context"), self.trn.text("node"), self.trn.text("right_context")]
        if self.current_kind == "dashboard":
            return [self.trn.text("category"), self.trn.text("measure"), self.trn.text("value")]
        if self.current_kind == "pos":
            if self.current_postagger_output_mode == "tag":
                return [self.trn.text("token"), self.trn.text("pos")]
            return [self.trn.text("token"), self.trn.text("lowercase"), self.trn.text("pos")]
        if self.current_kind == "tokenize":
            return {
                "tagged": [self.trn.text("token"), self.trn.text("tag")],
                "lines": [self.trn.text("line"), self.trn.text("result")],
                "tokenized": [self.trn.text("token")],
            }.get(self.current_tokenizer_mode or "tokenized", [self.trn.text("token")])
        return self.current_headers

    def _kind_label(self, result: TaskResult) -> str:
        if result.analysis_label_key:
            return self.trn.text(result.analysis_label_key)
        if result.kind == "frequency":
            if result.frequency_case_mode == "sensitive":
                return self.trn.text("frequency_sensitive")
            return self.trn.text("frequency_insensitive")
        if result.kind == "pos":
            return self.trn.text("pos_tagging")
        if result.kind == "dashboard":
            return self.trn.text("dashboard")
        if result.kind == "concordance":
            return self.trn.text("concordance")
        if result.kind == "ngrams":
            return self.trn.text("ngrams")
        mode = result.tokenizer_mode or "tokenized"
        return {
            "tokenized": self.trn.text("tokenization"),
            "tagged": self.trn.text("tokenizer_tags"),
            "lines": self.trn.text("line_tokenization"),
        }.get(mode, self.trn.text("tokenization"))

    def _kind_label_from_current(self) -> str:
        return {
            "frequency": self.trn.text("frequency"),
            "ngrams": self.trn.text("ngrams"),
            "concordance": self.trn.text("concordance"),
            "dashboard": self.trn.text("dashboard"),
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
        return status

    def _update_result_info(self) -> None:
        self.result_info.setVisible(self.current_kind is not None)
        self.analysis_summary_label.setText(self._status_for_current_result())
        tagged = self.current_kind == "tokenize" and self.current_tokenizer_mode == "tagged"
        self.tagged_note_label.setText(self.trn.text("tokenizer_tag_note"))
        self.tagged_note_label.setVisible(tagged)
