"""Styled desktop dialogs shared by settings, About and update checks."""
from __future__ import annotations

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices, QPixmap
from PySide6.QtWidgets import (
    QDialog, QFrame, QHBoxLayout, QLabel,
    QPushButton, QVBoxLayout, QWidget,
)

from app.config import APP_AUTHOR, APP_NAME, APP_VERSION
from app.i18n import Translator


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


class NoticeDialog(QDialog):
    def __init__(self, trn: Translator, title: str, body: str, parent: QWidget | None = None,
                 detail: str = '', confirm: str = '', download_url: str = '') -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setObjectName('NoticeDialog')
        self.setMinimumWidth(480)
        self.resize(540, 380)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 26, 28, 22)
        layout.setSpacing(18)
        layout.addWidget(label(trn.text('limit_eyebrow') if confirm else APP_NAME, 'DialogEyebrow'))
        layout.addWidget(label(title, 'DialogTitle'))
        layout.addWidget(label(body))
        if detail:
            details = card(trn.text('selected_limit') if confirm else trn.text('version'), detail)
            details.setMinimumHeight(88)
            layout.addWidget(details)
        layout.addStretch(1)
        footer = QHBoxLayout()
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
        layout.addLayout(footer)


class AboutDialog(QDialog):
    def __init__(self, trn: Translator, logo: QPixmap, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName('AboutDialog')
        self.setWindowTitle(trn.text('about_title'))
        self.setMinimumWidth(600)
        self.resize(660, 590)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 20)
        layout.setSpacing(16)

        hero = QFrame()
        hero.setObjectName('AboutHero')
        hero_layout = QVBoxLayout(hero)
        hero_layout.setContentsMargins(28, 24, 28, 26)
        hero_layout.setSpacing(10)
        top = QHBoxLayout()
        mark = QLabel()
        mark.setObjectName('AboutMark')
        mark.setPixmap(logo.scaled(124, 56, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        top.addWidget(mark)
        top.addStretch(1)
        version = label(f'v{APP_VERSION}', 'AboutVersion')
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
            '<a href="https://pypi.org/project/ts-postagger/">TS POSTagger</a> · spaCy', rich=True), 1)
        layout.addLayout(details)
        layout.addWidget(card(trn.text('scientific_reference'),
            '<b>SEZER, T. (2025)</b><br>'
            '<a href="https://tez.yok.gov.tr/UlusalTezMerkezi/TezGoster?key=Xau5rw3KuCgEuy-FuJQtsNVGSOOMCSQba2T5bZaDSDUTfOiTTVCpuBZPjDrUgB0i">'
            'Dizilerden birimlere: Bilişimsel dilbilim çerçevesinde bir birimlendirici tasarımı</a><br>'
            '[Doktora tezi, Hacettepe Üniversitesi]. Ulusal Tez Merkezi, Tez No. 959204', rich=True))
        layout.addStretch(1)
        footer = QHBoxLayout()
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
        layout.addLayout(footer)
