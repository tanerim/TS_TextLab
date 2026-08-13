"""Centralized QSS theme loading."""

from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path
from typing import Literal

from PySide6.QtCore import QSettings
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QApplication

ThemeName = Literal["system", "light", "dark"]


@dataclass(frozen=True)
class ThemePalette:
    name: str
    accent: str
    accent_hover: str
    accent_pressed: str
    focus: str
    background: str
    surface: str
    surface_alt: str
    panel: str
    text: str
    muted: str
    border: str
    border_strong: str
    hover: str
    selected: str
    selected_text: str
    success: str
    warning: str
    error: str
    pos_badge_bg: str
    pos_badge_text: str
    bar_fill: str


LIGHT_PALETTE = ThemePalette(
    name="light",
    accent="#2854A3",
    accent_hover="#21498F",
    accent_pressed="#1B3F7D",
    focus="#3B82F6",
    background="#F5F7FA",
    surface="#FFFFFF",
    surface_alt="#F8FAFC",
    panel="#FFFFFF",
    text="#18202B",
    muted="#667085",
    border="#D7DEE8",
    border_strong="#B8C2D2",
    hover="#EEF4FF",
    selected="#DCEAFF",
    selected_text="#102A56",
    success="#27815C",
    warning="#A15C07",
    error="#B42318",
    pos_badge_bg="#E8EEF8",
    pos_badge_text="#24436F",
    bar_fill="#D8E6FA",
)

ACCENTS = {
    "indigo": {
        "accent": "#2854A3",
        "accent_hover": "#21498F",
        "accent_pressed": "#1B3F7D",
        "focus": "#3B82F6",
        "selected": "#DCEAFF",
        "selected_text": "#102A56",
        "pos_badge_bg": "#E8EEF8",
        "pos_badge_text": "#24436F",
        "bar_fill": "#D8E6FA",
    },
    "petrol": {
        "accent": "#11606B",
        "accent_hover": "#0E535D",
        "accent_pressed": "#0B4650",
        "focus": "#178596",
        "selected": "#D9F0F3",
        "selected_text": "#073A42",
        "pos_badge_bg": "#E2F1F3",
        "pos_badge_text": "#164E56",
        "bar_fill": "#CDE9ED",
    },
    "teal": {
        "accent": "#147A6C",
        "accent_hover": "#106B5F",
        "accent_pressed": "#0C5C52",
        "focus": "#1BAA97",
        "selected": "#D9F3EF",
        "selected_text": "#073C35",
        "pos_badge_bg": "#DFF2EE",
        "pos_badge_text": "#15564D",
        "bar_fill": "#C9EAE4",
    },
    "violet": {
        "accent": "#5B4BA8",
        "accent_hover": "#504194",
        "accent_pressed": "#44377F",
        "focus": "#7868D8",
        "selected": "#E7E3FF",
        "selected_text": "#2F285D",
        "pos_badge_bg": "#ECE8FA",
        "pos_badge_text": "#4B3F82",
        "bar_fill": "#DED8F7",
    },
    "slate": {
        "accent": "#3E5C76",
        "accent_hover": "#354F66",
        "accent_pressed": "#2E4559",
        "focus": "#5D7F9F",
        "selected": "#E1E8EF",
        "selected_text": "#223548",
        "pos_badge_bg": "#E7ECF2",
        "pos_badge_text": "#33495F",
        "bar_fill": "#D5E0EA",
    },
    "emerald": {
        "accent": "#2F7D56",
        "accent_hover": "#286D4B",
        "accent_pressed": "#225E41",
        "focus": "#42A06F",
        "selected": "#DFF1E8",
        "selected_text": "#19442F",
        "pos_badge_bg": "#E4F1EA",
        "pos_badge_text": "#2A5940",
        "bar_fill": "#CFE8DA",
    },
    "burgundy": {
        "accent": "#8A3C55",
        "accent_hover": "#78344A",
        "accent_pressed": "#682D40",
        "focus": "#B35C79",
        "selected": "#F3E2E8",
        "selected_text": "#562638",
        "pos_badge_bg": "#F2E6EA",
        "pos_badge_text": "#6A3448",
        "bar_fill": "#EAD4DC",
    },
    "amber": {
        "accent": "#8A5A12",
        "accent_hover": "#794F10",
        "accent_pressed": "#68450E",
        "focus": "#B47A21",
        "selected": "#F4E9D2",
        "selected_text": "#563A0E",
        "pos_badge_bg": "#F2E8D7",
        "pos_badge_text": "#6A4B1E",
        "bar_fill": "#EBDDBE",
    },
}

DARK_PALETTE = ThemePalette(
    name="dark",
    accent="#7AA7FF",
    accent_hover="#94B8FF",
    accent_pressed="#5F93F2",
    focus="#9CC2FF",
    background="#111827",
    surface="#1B2433",
    surface_alt="#202B3C",
    panel="#151E2C",
    text="#E7ECF4",
    muted="#A5AFBF",
    border="#344052",
    border_strong="#4A5870",
    hover="#243247",
    selected="#2C4266",
    selected_text="#F6F9FF",
    success="#6CC39B",
    warning="#F2B15B",
    error="#F97066",
    pos_badge_bg="#293B56",
    pos_badge_text="#C8DAFF",
    bar_fill="#263A5A",
)

DARK_ACCENTS = {
    "indigo": {
        "accent": "#7AA7FF",
        "accent_hover": "#94B8FF",
        "accent_pressed": "#5F93F2",
        "focus": "#9CC2FF",
        "selected": "#2C4266",
        "selected_text": "#F6F9FF",
        "pos_badge_bg": "#293B56",
        "pos_badge_text": "#C8DAFF",
        "bar_fill": "#263A5A",
    },
    "petrol": {
        "accent": "#58C2D0",
        "accent_hover": "#70D1DD",
        "accent_pressed": "#3AAEBD",
        "focus": "#7BDCE8",
        "selected": "#214650",
        "selected_text": "#F3FCFD",
        "pos_badge_bg": "#243E48",
        "pos_badge_text": "#BDECF2",
        "bar_fill": "#233F4A",
    },
    "teal": {
        "accent": "#5FD0BB",
        "accent_hover": "#77DDCB",
        "accent_pressed": "#43BDA7",
        "focus": "#89E8D8",
        "selected": "#244B45",
        "selected_text": "#F3FFFC",
        "pos_badge_bg": "#25433F",
        "pos_badge_text": "#C6F4EA",
        "bar_fill": "#244640",
    },
    "violet": {
        "accent": "#A99BFF",
        "accent_hover": "#BBAFFF",
        "accent_pressed": "#8D7EF2",
        "focus": "#C7BEFF",
        "selected": "#403A64",
        "selected_text": "#FBFAFF",
        "pos_badge_bg": "#393451",
        "pos_badge_text": "#DDD7FF",
        "bar_fill": "#383453",
    },
    "slate": {
        "accent": "#8FAEC8",
        "accent_hover": "#A5C0D7",
        "accent_pressed": "#7598B7",
        "focus": "#B5D0E5",
        "selected": "#33485B",
        "selected_text": "#F5FAFF",
        "pos_badge_bg": "#2E3F50",
        "pos_badge_text": "#D0E3F3",
        "bar_fill": "#2D4154",
    },
    "emerald": {
        "accent": "#78C8A0",
        "accent_hover": "#8DD6B1",
        "accent_pressed": "#5DBA8A",
        "focus": "#A4E5C2",
        "selected": "#2D4B3B",
        "selected_text": "#F4FFF9",
        "pos_badge_bg": "#2B4438",
        "pos_badge_text": "#CDF3DE",
        "bar_fill": "#294739",
    },
    "burgundy": {
        "accent": "#D78AA4",
        "accent_hover": "#E49CB4",
        "accent_pressed": "#C97290",
        "focus": "#F0B4C7",
        "selected": "#563747",
        "selected_text": "#FFF7FA",
        "pos_badge_bg": "#4B3340",
        "pos_badge_text": "#F4CCD9",
        "bar_fill": "#4B3541",
    },
    "amber": {
        "accent": "#D4A45C",
        "accent_hover": "#E2B775",
        "accent_pressed": "#BF8E41",
        "focus": "#F0CB8D",
        "selected": "#55442B",
        "selected_text": "#FFF9EF",
        "pos_badge_bg": "#4B3D2B",
        "pos_badge_text": "#F2D7A8",
        "bar_fill": "#4B3E2C",
    },
}


def effective_theme(theme: ThemeName) -> Literal["light", "dark"]:
    if theme != "system":
        return theme

    hints = QGuiApplication.styleHints()
    scheme = hints.colorScheme()
    return "dark" if scheme.name.lower() == "dark" else "light"


def palette_for(theme: ThemeName, accent: str = "indigo") -> ThemePalette:
    dark = effective_theme(theme) == "dark"
    palette = DARK_PALETTE if dark else LIGHT_PALETTE
    accents = DARK_ACCENTS if dark else ACCENTS
    values = accents.get(accent, accents["indigo"])
    return replace(palette, **values)


def load_qss(theme: ThemeName, accent: str = "indigo") -> str:
    palette = palette_for(theme, accent)
    qss_path = Path(__file__).with_name(f"{palette.name}.qss")
    return qss_path.read_text(encoding="utf-8").format(**palette.__dict__)


def apply_theme(app: QApplication, settings: QSettings) -> ThemePalette:
    theme = settings.value("theme", "system", str)
    if theme not in {"system", "light", "dark"}:
        theme = "system"
    accent = settings.value("accent", "indigo", str)
    if accent not in ACCENTS:
        accent = "indigo"
    app.setStyleSheet(load_qss(theme, accent))  # type: ignore[arg-type]
    return palette_for(theme, accent)  # type: ignore[arg-type]
