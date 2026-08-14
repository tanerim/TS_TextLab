"""TS Tokenizer integration."""

from __future__ import annotations

from dataclasses import dataclass
from collections import Counter
from typing import Iterable, Literal

from app.errors import DependencyUnavailableError, EmptyInputError, TextLabError

TokenizerMode = Literal["tokenized", "tagged", "lines", "tagged_lines"]
FrequencyCaseMode = Literal["sensitive", "insensitive"]


@dataclass(frozen=True)
class TokenizerResult:
    mode: TokenizerMode
    headers: list[str]
    rows: list[tuple[str, ...]]
    copy_text: str


class TokenizerService:
    """Thin adapter around the external ts-tokenizer package."""

    def __init__(self) -> None:
        try:
            from ts_tokenizer import CharFix, tokenize
        except ImportError as exc:
            raise DependencyUnavailableError(
                "`ts-tokenizer` kurulu değil. Geliştirme ortamında `pip install -r requirements.txt` çalıştırın."
            ) from exc
        self._tokenize = tokenize
        self._char_fix = CharFix

    def tokenize(self, text: str, mode: TokenizerMode = "tokenized") -> TokenizerResult:
        cleaned = text.strip()
        if not cleaned:
            raise EmptyInputError("Lütfen işlenecek bir metin girin.")

        try:
            if mode in {"lines", "tagged_lines"}:
                return self._tokenize_by_line(cleaned, mode)
            result = self._tokenize(cleaned, mode)
        except Exception as exc:  # pragma: no cover - external library guard
            raise TextLabError(f"Tokenization sırasında hata oluştu: {exc}") from exc

        return self._normalize_result(mode, result)

    def tokens_for_pos(self, text: str) -> list[str]:
        tokenized = self.tokenize(text, "tokenized")
        return [row[0] for row in tokenized.rows if row and row[0].strip()]

    def frequency(self, text: str, case_mode: FrequencyCaseMode = "insensitive") -> TokenizerResult:
        tokens = self.tokens_for_pos(text)
        if case_mode == "insensitive":
            tokens = [self._char_fix.tr_lowercase(token) for token in tokens]
        counts = Counter(tokens)
        rows = [
            (token, str(count))
            for token, count in sorted(counts.items(), key=lambda item: (-item[1], self._sort_key(item[0])))
        ]
        return TokenizerResult(
            mode="tokenized",
            headers=["Token", "Count"],
            rows=rows,
            copy_text="\n".join("\t".join(row) for row in rows),
        )

    def _sort_key(self, value: str) -> str:
        return self._char_fix.tr_lowercase(value)

    def _tokenize_by_line(self, text: str, mode: TokenizerMode) -> TokenizerResult:
        source_lines = [line.strip() for line in text.splitlines() if line.strip()]
        if not source_lines:
            raise EmptyInputError("Lütfen işlenecek bir metin girin.")

        if mode == "lines":
            rows: list[tuple[str, ...]] = []
            for line_number, line in enumerate(source_lines, start=1):
                tokenized_line = str(self._tokenize(line, "lines")).strip()
                if tokenized_line:
                    rows.append((str(line_number), tokenized_line))
            return TokenizerResult(
                mode=mode,
                headers=["Line", "Result"],
                rows=rows,
                copy_text="\n".join(row[1] for row in rows),
            )

        tagged_rows: list[tuple[str, ...]] = []
        for line_number, line in enumerate(source_lines, start=1):
            line_result = self._tokenize(line, "tagged_lines")
            pairs = self._normalize_pairs(line_result)
            if pairs:
                tagged_rows.extend(pairs)
        return TokenizerResult(
            mode=mode,
            headers=["Token", "Tag"],
            rows=tagged_rows,
            copy_text=repr(tagged_rows),
        )

    @staticmethod
    def _normalize_result(mode: TokenizerMode, result: object) -> TokenizerResult:
        if mode == "tagged_lines":
            rows = TokenizerService._normalize_pairs(result)
            return TokenizerResult(
                mode=mode,
                headers=["Token", "Tag"],
                rows=rows,
                copy_text="\n".join("\t".join(row) for row in rows),
            )

        if isinstance(result, str):
            lines = [line.strip() for line in result.splitlines() if line.strip()]
            if mode == "tagged":
                rows = [tuple(line.split("\t", 1)) if "\t" in line else (line, "") for line in lines]
                return TokenizerResult(mode=mode, headers=["Token", "Tag"], rows=rows, copy_text=result)
            if mode == "lines":
                return TokenizerResult(
                    mode=mode,
                    headers=["Line"],
                    rows=[(line,) for line in lines],
                    copy_text=result,
                )
            return TokenizerResult(
                mode=mode,
                headers=["Token"],
                rows=[(line,) for line in lines],
                copy_text=result,
            )

        rows = [(token,) for token in TokenizerService._normalize_tokens(result)]
        return TokenizerResult(
            mode=mode,
            headers=["Token"],
            rows=rows,
            copy_text="\n".join(row[0] for row in rows),
        )

    @staticmethod
    def _normalize_pairs(result: object) -> list[tuple[str, str]]:
        if isinstance(result, str):
            return [
                tuple(line.split("\t", 1)) if "\t" in line else (line, "")
                for line in result.splitlines()
                if line.strip()
            ]

        if isinstance(result, Iterable):
            rows: list[tuple[str, str]] = []
            for item in result:
                if isinstance(item, (list, tuple)) and len(item) >= 2:
                    rows.append((str(item[0]), str(item[1])))
                elif str(item).strip():
                    rows.append((str(item), ""))
            return rows

        raise TextLabError("TS Tokenizer beklenmeyen bir çıktı döndürdü.")

    @staticmethod
    def _normalize_tokens(result: object) -> list[str]:
        if isinstance(result, Iterable):
            tokens: list[str] = []
            for item in result:
                if isinstance(item, (list, tuple)):
                    tokens.extend(str(part) for part in item if str(part).strip())
                elif str(item).strip():
                    tokens.append(str(item))
            return tokens

        raise TextLabError("TS Tokenizer beklenmeyen bir çıktı döndürdü.")
