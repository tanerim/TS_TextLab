"""Small runtime translation helper for Turkish and English UI text."""

from __future__ import annotations

import locale


TRANSLATIONS = {
    "tr": {
        "input_placeholder": "Türkçe metin yazın veya yapıştırın...",
        "tokenization_mode": "Birimlendirme Modu",
        "tokenize": "Birimlendir",
        "pos_tag": "Sözcük Türü Etiketle",
        "frequency": "Sıklık",
        "copy_result": "Sonucu Kopyala",
        "clear_input": "Girişi Temizle",
        "clear_result": "Sonucu Temizle",
        "ready": "Hazır",
        "processing": "İşleniyor...",
        "token": "Birim",
        "pos": "POS",
        "tag": "Etiket",
        "line": "Satır",
        "result": "Sonuç",
        "error": "Hata",
        "operation_failed": "İşlem tamamlanamadı",
        "no_result": "Kopyalanacak sonuç yok.",
        "copied": "Sonuç panoya kopyalandı.",
        "cleared": "Sonuç temizlendi.",
        "processed": "{count} kayıt işlendi.",
        "tokenizer_tag_note": "Verilen etiketler sözcük türü etiketleri değildir; verilen birimin işlevini tanımlar.",
        "count": "Sıklık",
        "help": "Yardım",
        "settings": "Ayarlar",
        "language": "Dil",
        "turkish": "Türkçe",
        "english": "English",
        "guide": "Kullanma Kılavuzu",
        "more_info": "Ek Bilgiler",
        "about": "Hakkında",
        "about_title": "TS TextLab Hakkında",
        "about_body": "{app} {version}\n\nTürkçe metinler için yerel metin işleme uygulaması.",
        "guide_body": "1. Metni giriş alanına yazın veya yapıştırın.\n2. Birimlendirme Modu seçimini yapın.\n3. Birimlendir veya Sözcük Türü Etiketle düğmesine basın.\n4. Sonucu panoya kopyalayabilirsiniz.",
        "info_body": "TS TextLab metinleri yerel olarak işler.",
        "update_title": "Yeni güncelleme var",
        "update_body": "Yeni sürüm mevcut: {latest}\nMevcut sürüm: {current}",
        "up_to_date": "Güncel sürüm kullanılıyor.",
        "version_check_failed": "Güncelleme denetimi yapılamadı.",
    },
    "en": {
        "input_placeholder": "Type or paste Turkish text...",
        "tokenization_mode": "Tokenization Mode",
        "tokenize": "Tokenize",
        "pos_tag": "POSTag",
        "frequency": "Frequency",
        "copy_result": "Copy Result",
        "clear_input": "Clear Input",
        "clear_result": "Clear Result",
        "ready": "Ready",
        "processing": "Processing...",
        "token": "Token",
        "pos": "POS",
        "tag": "Tag",
        "line": "Line",
        "result": "Result",
        "error": "Error",
        "operation_failed": "Operation failed",
        "no_result": "There is no result to copy.",
        "copied": "Result copied to clipboard.",
        "cleared": "Result cleared.",
        "processed": "{count} rows processed.",
        "tokenizer_tag_note": "Given tags are not part-of-speech tags but they define the function of the given string.",
        "count": "Count",
        "help": "Help",
        "settings": "Settings",
        "language": "Language",
        "turkish": "Türkçe",
        "english": "English",
        "guide": "User Guide",
        "more_info": "More Info",
        "about": "About",
        "about_title": "About TS TextLab",
        "about_body": "{app} {version}\n\nA local desktop app for Turkish tokenization and POS tagging.",
        "guide_body": "1. Type or paste text into the input field.\n2. Select a Tokenization Mode.\n3. Press Tokenize or POSTag.\n4. Copy the result when needed.",
        "info_body": "TS TextLab processes text locally. No text is sent to a server, except the app may check the version endpoint for updates.",
        "update_title": "Update Available",
        "update_body": "New version available: {latest}\nCurrent version: {current}",
        "up_to_date": "You are using the latest version.",
        "version_check_failed": "Could not check for updates.",
    },
}


def system_language() -> str:
    language, _ = locale.getlocale()
    if language and language.lower().startswith("tr"):
        return "tr"
    return "en"


class Translator:
    def __init__(self, language: str | None = None) -> None:
        self.language = language or system_language()
        if self.language not in TRANSLATIONS:
            self.language = "en"

    def text(self, key: str, **kwargs: object) -> str:
        value = TRANSLATIONS[self.language].get(key, TRANSLATIONS["en"].get(key, key))
        return value.format(**kwargs) if kwargs else value
