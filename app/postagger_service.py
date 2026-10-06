"""TS POSTagger package integration."""

from __future__ import annotations

from typing import Literal
import re

from app.errors import DependencyUnavailableError, EmptyInputError, TextLabError

PostaggerOutputMode = Literal["full", "tag"]


class PosTaggerService:
    """Thin adapter around the external ts-postagger package."""

    def __init__(self) -> None:
        self._pos = None
        self._cached_text = None
        self._cached_tokens = None

    def tag(self, text: str) -> list[tuple[str, str]]:
        tokens = self.tokens(text)
        return [(token.text, token.pos or "-") for token in tokens]

    def format_output(self, text: str, mode: PostaggerOutputMode = "full") -> tuple[list[str], list[tuple[str, ...]], str]:
        tokens = self.tokens(text)
        headers = ["Token", "Lowercase", "POS"] if mode == "full" else ["Token", "POS"]
        rows: list[tuple[str, ...]] = []
        copy_lines: list[str] = []

        for token in tokens:
            if token.token_type == "XML_Tag":
                row = (token.text,)
            elif mode == "full":
                row = (token.text, token.lower, token.pos or "-")
            else:
                row = (token.text, token.pos or "-")
            rows.append(row)
            copy_lines.append("\t".join(row))

        return headers, rows, "\n".join(copy_lines)

    def tokens(self, text: str):
        cleaned = text.strip()
        if not cleaned:
            raise EmptyInputError("Lütfen işlenecek bir metin girin.")

        pos = self._load_pos_function()
        try:
            if cleaned == self._cached_text:
                return self._cached_tokens
            tokens = []
            # Bound model tensors; prefer sentence/line boundaries, then whitespace.
            start = 0
            while start < len(cleaned):
                end = min(start + 32_000, len(cleaned))
                if end < len(cleaned):
                    boundaries = list(re.finditer(r"[.!?]\s+|\n+", cleaned[start:end]))
                    if boundaries:
                        end = start + boundaries[-1].end()
                    else:
                        boundary = cleaned.rfind(" ", start, end)
                        if boundary > start:
                            end = boundary + 1
                        else:
                            following = re.search(r"\s", cleaned[end:])
                            end = end + following.end() if following else len(cleaned)
                    # Do not split an XML tag containing whitespace.
                    if cleaned.rfind("<", start, end) > cleaned.rfind(">", start, end):
                        close = cleaned.find(">", end)
                        if close >= 0:
                            end = close + 1
                tokens.extend(pos(cleaned[start:end]))
                start = end
            self._cached_text = cleaned
            self._cached_tokens = tokens
        except Exception as exc:  # pragma: no cover - external library guard
            raise TextLabError(f"POS tagging sırasında hata oluştu: {exc}") from exc

        return tokens

    def _load_pos_function(self):
        if self._pos is not None:
            return self._pos

        try:
            from ts_postagger import pos
        except ImportError as exc:
            raise DependencyUnavailableError(
                "`ts-postagger` kurulu değil. Geliştirme ortamında `pip install -r requirements.txt` çalıştırın."
            ) from exc

        self._pos = pos
        return self._pos
