"""Styled desktop dialogs shared by settings, About and update checks."""
from __future__ import annotations

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices, QPixmap
from PySide6.QtWidgets import (
    QDialog, QFrame, QHBoxLayout, QLabel,
    QPushButton, QScrollArea, QSizePolicy, QVBoxLayout, QWidget,
)

from app.config import APP_AUTHOR, APP_NAME, APP_VERSION
from app.i18n import Translator


class ContentDialog(QDialog):
    """Fit natural content height to the screen; scroll the body if necessary."""

    def __init__(self, parent: QWidget | None = None, preferred_width: int = 660) -> None:
        super().__init__(parent)
        self.preferred_width = preferred_width
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        self.body_scroll = QScrollArea()
        self.body_scroll.setObjectName('DialogScroll')
        self.body_scroll.setWidgetResizable(True)
        self.body_scroll.setFrameShape(QFrame.NoFrame)
        self.body_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.body = QWidget()
        self.body.setObjectName('DialogBody')
        self.body_layout = QVBoxLayout(self.body)
        self.body_layout.setContentsMargins(24, 24, 24, 12)
        self.body_layout.setSpacing(16)
        self.body_scroll.setWidget(self.body)
        root.addWidget(self.body_scroll, 1)
        self.footer = QFrame()
        self.footer.setObjectName('DialogFooter')
        self.footer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.footer_layout = QHBoxLayout(self.footer)
        self.footer_layout.setContentsMargins(24, 12, 24, 16)
        self.footer_layout.setSpacing(10)
        root.addWidget(self.footer)

    def content_height(self, width: int) -> int:
        layout = self.body_layout
        return max(layout.minimumSize().height(), layout.totalHeightForWidth(width)
                   if layout.hasHeightForWidth() else layout.sizeHint().height())

    def fit_to_content(self) -> None:
        self.ensurePolished()
        for child in self.findChildren(QWidget):
            child.ensurePolished()
        self.body_layout.invalidate()
        available = self.screen().availableGeometry()
        # Reserve space for the OS title bar and window borders.
        width = min(self.preferred_width, max(1, available.width() - 32))
        max_height = max(1, available.height() - 48)
        footer_height = self.footer.sizeHint().height()
        body_height = self.content_height(width)
        if body_height + footer_height > max_height:
            body_height = self.content_height(width - self.body_scroll.verticalScrollBar().sizeHint().width())
        self.setMinimumSize(min(480, width), min(240, max_height))
        self.body.setMinimumHeight(body_height)
        self.resize(width, min(body_height + footer_height, max_height))
        self.layout().activate()
        self._sync_body_height()

    def _sync_body_height(self) -> None:
        width = self.body_scroll.viewport().width()
        if width > 0:
            height = self.content_height(width)
            if self.body.minimumHeight() != height:
                self.body.setMinimumHeight(height)

    def showEvent(self, event) -> None:  # type: ignore[override]
        self.fit_to_content()
        super().showEvent(event)

    def resizeEvent(self, event) -> None:  # type: ignore[override]
        super().resizeEvent(event)
        self.layout().activate()
        self._sync_body_height()


def label(text: str, name: str = 'DialogMuted') -> QLabel:
    widget = QLabel(text)
    widget.setObjectName(name)
    widget.setWordWrap(True)
    widget.setTextFormat(Qt.PlainText)
    return widget


def card(title: str, body: str, rich: bool = False) -> QFrame:
    frame = QFrame()
    frame.setObjectName('DialogCard')
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(20, 16, 20, 18)
    layout.setSpacing(8)
    layout.addWidget(label(title, 'DialogSection'))
    text = label(body)
    if rich:
        text.setText(body.replace('<a ', '<a style="color:#245B9E; text-decoration:none;" '))
        text.setTextFormat(Qt.RichText)
        text.setOpenExternalLinks(True)
        text.setTextInteractionFlags(Qt.TextBrowserInteraction)
    layout.addWidget(text)
    return frame


class NoticeDialog(ContentDialog):
    def __init__(self, trn: Translator, title: str, body: str, parent: QWidget | None = None,
                 detail: str = '', confirm: str = '', download_url: str = '') -> None:
        super().__init__(parent, preferred_width=560)
        self.setWindowTitle(title)
        self.setObjectName('NoticeDialog')
        layout = self.body_layout
        layout.setContentsMargins(28, 26, 28, 16)
        layout.setSpacing(18)
        layout.addWidget(label(trn.text('limit_eyebrow') if confirm else APP_NAME, 'DialogEyebrow'))
        layout.addWidget(label(title, 'DialogTitle'))
        layout.addWidget(label(body))
        if detail:
            details = card(trn.text('selected_limit') if confirm else trn.text('version'), detail)
            details.setMinimumHeight(88)
            layout.addWidget(details)
        footer = self.footer_layout
        footer.setSpacing(10)
        footer.addStretch(1)
        if confirm:
            cancel = QPushButton(trn.text('cancel'))
            cancel.setObjectName('DialogSecondaryButton')
            cancel.setDefault(True)
            cancel.clicked.connect(self.reject)
            footer.addWidget(cancel)
        if download_url:
            download = QPushButton(trn.text('download_update'))
            download.setObjectName('DialogPrimaryButton')
            download.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(download_url)))
            footer.addWidget(download)
        action = QPushButton(confirm or trn.text('ok'))
        action.setObjectName('DialogPrimaryButton' if confirm or not download_url else 'DialogSecondaryButton')
        action.clicked.connect(self.accept)
        footer.addWidget(action)
        self.fit_to_content()


class AboutDialog(ContentDialog):
    def __init__(self, trn: Translator, logo: QPixmap, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName('AboutDialog')
        self.setWindowTitle(trn.text('about_title'))
        layout = self.body_layout

        hero = QFrame()
        hero.setObjectName('AboutHero')
        hero_layout = QVBoxLayout(hero)
        hero_layout.setContentsMargins(28, 24, 28, 26)
        hero_layout.setSpacing(10)
        top = QHBoxLayout()
        mark = QLabel()
        mark.setObjectName('AboutMark')
        mark.setAlignment(Qt.AlignCenter)
        ratio = self.devicePixelRatioF()
        scaled_logo = logo.scaled(round(160 * ratio), round(64 * ratio), Qt.KeepAspectRatio, Qt.SmoothTransformation)
        scaled_logo.setDevicePixelRatio(ratio)
        mark.setPixmap(scaled_logo)
        mark.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        mark.ensurePolished()
        mark.setMinimumSize(mark.sizeHint())
        top.addWidget(mark)
        top.addStretch(1)
        version = label(f'v{APP_VERSION}', 'AboutVersion')
        version.setWordWrap(False)
        version.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        top.addWidget(version)
        hero_layout.addLayout(top)
        hero_layout.addSpacing(12)
        hero_layout.addWidget(label(APP_NAME, 'AboutTitle'))
        hero_layout.addWidget(label(trn.text('about_tagline'), 'AboutTagline'))
        hero_layout.addSpacing(4)
        hero_layout.addWidget(label(f'{APP_AUTHOR}  ·  TS Corpus', 'AboutCredit'))
        layout.addWidget(hero)

        details = QHBoxLayout()
        details.setSpacing(14)
        details.addWidget(card(trn.text('local_processing_statement'), trn.text('no_upload_statement')), 1)
        details.addWidget(card(trn.text('powered_by'),
            '<a href="https://pypi.org/project/ts-tokenizer/">TS Tokenizer</a><br>'
            '<a href="https://pypi.org/project/ts-postagger/">TS POSTagger</a>', rich=True), 1)
        layout.addLayout(details)
        layout.addWidget(card(trn.text('scientific_reference'),
            '<b>SEZER, T. (2025)</b><br>'
            '<a href="https://tez.yok.gov.tr/UlusalTezMerkezi/TezGoster?key=Xau5rw3KuCgEuy-FuJQtsNVGSOOMCSQba2T5bZaDSDUTfOiTTVCpuBZPjDrUgB0i">'
            'Dizilerden birimlere: Bilişimsel dilbilim çerçevesinde bir birimlendirici tasarımı</a><br>'
            '[Doktora tezi, Hacettepe Üniversitesi]. Ulusal Tez Merkezi, Tez No. 959204', rich=True))
        footer = self.footer_layout
        website = label('<a style="color:#245B9E; text-decoration:none;" href="https://tscorpus.com/">tscorpus.com ↗</a>')
        website.setTextFormat(Qt.RichText)
        website.setOpenExternalLinks(True)
        footer.addWidget(website)
        footer.addStretch(1)
        close = QPushButton(trn.text('close'))
        close.setObjectName('DialogPrimaryButton')
        close.setDefault(True)
        close.clicked.connect(self.accept)
        footer.addWidget(close)
        self.fit_to_content()
