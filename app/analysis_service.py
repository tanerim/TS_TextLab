"""Shared token-based analysis helpers."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

from app.postagger_service import PosTaggerService
from app.tokenizer_service import FrequencyCaseMode, TokenizerMode, TokenizerService


LEXICAL_TAGS = frozenset({"", "Valid_Word", "Apostrophed", "OOV", "One_Char_Fixed"})
PUNCTUATION_CHARS = frozenset(".!?;:,-()[]{}\"'`…")


@dataclass(frozen=True)
class TokenInfo:
    surface: str
    position: int
    tokenizer: str
    pos: str = "-"
    paragraph: int = 1

    @property
    def length(self) -> int:
        return len(self.surface)


@dataclass(frozen=True)
class AnalysisDocument:
    tokens: list[TokenInfo]

    @property
    def lexical_tokens(self) -> list[TokenInfo]:
        return [token for token in self.tokens if is_lexical(token)]

    @property
    def paragraphs(self) -> list[list[TokenInfo]]:
        grouped: list[list[TokenInfo]] = []
        current_paragraph = 0
        for token in self.tokens:
            if token.paragraph != current_paragraph:
                grouped.append([])
                current_paragraph = token.paragraph
            grouped[-1].append(token)
        return grouped

    @property
    def sentences(self) -> list[list[TokenInfo]]:
        return self.paragraphs


class AnalysisService:
    def __init__(self, tokenizer_service: TokenizerService, postagger_service: PosTaggerService) -> None:
        self.tokenizer_service = tokenizer_service
        self.postagger_service = postagger_service

    def build_document(self, text: str, include_pos: bool = False) -> AnalysisDocument:
        analysis_text = _strip_tabular_annotations(text)
        if include_pos:
            return self._build_postagger_document(analysis_text)

        tagged = self.tokenizer_service.tokenize(analysis_text, "tagged_lines")
        pairs = [(row[0], row[1] if len(row) > 1 else "") for row in tagged.rows if row and row[0].strip()]
        pos_by_position: list[str] = ["-"] * len(pairs)

        paragraph_sequence = self._paragraph_sequence(analysis_text)
        tokens: list[TokenInfo] = []
        for position, ((surface, tokenizer_tag), pos) in enumerate(zip(pairs, pos_by_position, strict=True), start=1):
            tag = normalize_tokenizer_tag(surface, tokenizer_tag)
            paragraph = paragraph_sequence[position - 1] if position - 1 < len(paragraph_sequence) else 1
            tokens.append(TokenInfo(surface=surface, position=position, tokenizer=tag, pos=pos, paragraph=paragraph))
        return AnalysisDocument(tokens=tokens)

    def _build_postagger_document(self, text: str) -> AnalysisDocument:
        tokens = [
            TokenInfo(
                surface=token.text,
                position=position,
                tokenizer=token.token_type,
                pos=token.pos or "-",
                paragraph=1,
            )
            for position, token in enumerate(self.postagger_service.tokens(text), start=1)
        ]
        return AnalysisDocument(tokens=tokens)

    def _paragraph_sequence(self, text: str) -> list[int]:
        sequence: list[int] = []
        paragraph = 1
        for line in text.splitlines() or [text]:
            if line.strip():
                for token in self.tokenizer_service.tokenize(line, "tokenized").rows:
                    if token and token[0].strip():
                        sequence.append(paragraph)
            paragraph += 1
        return sequence


def tokenization_rows(document: AnalysisDocument, mode: TokenizerMode) -> tuple[list[str], list[tuple[str, ...]], str]:
    if mode == "tagged":
        rows = [(token.surface, token.tokenizer) for token in document.tokens]
        return ["Token", "Tag"], rows, "\n".join("\t".join(row) for row in rows)
    if mode == "lines":
        rows = []
        for paragraph in document.paragraphs:
            if paragraph:
                rows.append((str(paragraph[0].paragraph), " ".join(token.surface for token in paragraph)))
        return ["Line", "Result"], rows, "\n".join(row[1] for row in rows)
    rows = [(token.surface,) for token in document.tokens]
    return ["Token"], rows, "\n".join(token.surface for token in document.tokens)


def frequency_rows(
    document: AnalysisDocument, case_mode: FrequencyCaseMode, lowercase_func=None
) -> tuple[list[str], list[tuple[str, ...]], str]:
    values = [token.surface for token in document.lexical_tokens]
    if case_mode == "insensitive":
        lower = lowercase_func or (lambda value: value.casefold())
        values = [lower(value) for value in values]
    counts = Counter(values)
    rows = [(token, str(count)) for token, count in _sorted_counts(counts)]
    return ["Token", "Count"], rows, "\n".join("\t".join(row) for row in rows)


def dashboard_rows(text: str, document: AnalysisDocument) -> tuple[list[str], list[tuple[str, ...]], str]:
    lexical = document.lexical_tokens
    token_lengths = [token.length for token in lexical]
    type_counts = Counter(token_type(token) for token in document.tokens if token_type(token) != "XML_Tag")
    pos_counts = Counter(
        token.pos
        for token in document.tokens
        if token.tokenizer != "XML_Tag" and token.pos and token.pos != "-"
    )
    metric_rows = [
        ("Metric", "Characters", str(len(text))),
        ("Metric", "Tokens", str(len([token for token in document.tokens if token.tokenizer != "XML_Tag"]))),
        ("Metric", "Lexical tokens", str(len(lexical))),
        ("Metric", "Unique tokens", str(len({token.surface.casefold() for token in lexical}))),
        ("Metric", "Sentences", str(len(document.paragraphs))),
        ("Metric", "Mean token length", _mean(token_lengths)),
        ("Metric", "Type-token ratio", _ratio(len({token.surface.casefold() for token in lexical}), len(lexical))),
    ]
    type_rows = [("Token Type", name, str(count)) for name, count in _sorted_counts(type_counts)]
    pos_rows = [("POS", name, str(count)) for name, count in _sorted_counts(pos_counts)]
    rows = metric_rows + type_rows + pos_rows
    return ["Section", "Label", "Value"], rows, "\n".join("\t".join(row) for row in rows)


def token_composition_rows(document: AnalysisDocument) -> tuple[list[str], list[tuple[str, ...]], str]:
    counts = Counter(token.tokenizer for token in document.tokens)
    rows = _count_percent_rows(counts, len(document.tokens))
    return ["Category", "Count", "Percentage"], rows, "\n".join("\t".join(row) for row in rows)


def lexical_coverage_rows(document: AnalysisDocument) -> tuple[list[str], list[tuple[str, ...]], str]:
    counts = Counter(
        token.surface
        for token in document.tokens
        if token.tokenizer == "OOV" and token.surface.isalpha()
    )
    rows = [(token, str(count)) for token, count in _sorted_counts(counts)]
    return ["Token", "Count"], rows, "\n".join("\t".join(row) for row in rows)


def ngram_rows(
    document: AnalysisDocument, n: int, included_types: set[str]
) -> tuple[list[str], list[tuple[str, ...]], str]:
    tokens = [token.surface for token in document.tokens if token_type(token) in included_types]
    counts = Counter(" ".join(tokens[index : index + n]) for index in range(max(0, len(tokens) - n + 1)))
    rows = [(ngram, str(count)) for ngram, count in _sorted_counts(counts)]
    return ["N-gram", "Count"], rows, "\n".join("\t".join(row) for row in rows)


def concordance_rows(
    document: AnalysisDocument, query: str, span: int
) -> tuple[list[str], list[tuple[str, ...]], str]:
    needle = query.casefold().strip()
    rows: list[tuple[str, ...]] = []
    if not needle:
        return ["Left", "Node", "Right"], rows, ""
    for index, token in enumerate(document.tokens):
        if token.surface.casefold() != needle:
            continue
        left = " ".join(item.surface for item in document.tokens[max(0, index - span) : index])
        right = " ".join(item.surface for item in document.tokens[index + 1 : index + span + 1])
        rows.append((left, token.surface, right))
    return ["Left", "Node", "Right"], rows, "\n".join("\t".join(row) for row in rows)


def normalize_tokenizer_tag(surface: str, tag: str) -> str:
    if _is_xml_tag(surface):
        return "XML_Tag"

    clean = tag.strip() or "Valid_Word"
    if clean in {"Mention", "Hashtag", "URL", "Emoji", "Email", "Date", "Time", "OOV", "Punctuation"}:
        return clean
    if surface.startswith("@") and len(surface) > 1:
        return "Mention"
    if surface.startswith("#") and len(surface) > 1:
        return "Hashtag"
    if surface.startswith(("http://", "https://", "www.")):
        return "URL"
    if "@" in surface and "." in surface and not surface.startswith("@"):
        return "Email"
    if all(char in PUNCTUATION_CHARS for char in surface):
        return "Punctuation"
    return clean


def token_type(token: TokenInfo) -> str:
    if token.tokenizer == "XML_Tag":
        return "XML_Tag"
    if is_lexical(token):
        return "Words"
    if token.tokenizer in {"Punctuation", "Punc"}:
        return "Punctuation"
    if token.tokenizer in {"URL", "Full_URL", "Web_URL"}:
        return "URLs"
    if token.tokenizer == "Mention":
        return "Mentions"
    if token.tokenizer == "Hashtag":
        return "Hashtags"
    return "Other"


def is_lexical(token: TokenInfo) -> bool:
    return token.tokenizer in LEXICAL_TAGS and any(char.isalnum() for char in token.surface)


def is_punctuation(token: TokenInfo) -> bool:
    return token.tokenizer in {"Punctuation", "Punc"} or all(char in PUNCTUATION_CHARS for char in token.surface)


def _is_xml_tag(surface: str) -> bool:
    value = surface.strip()
    return len(value) >= 3 and value.startswith("<") and value.endswith(">")


def _strip_tabular_annotations(text: str) -> str:
    lines = text.splitlines()
    if not any("\t" in line for line in lines):
        return text

    stripped_lines: list[str] = []
    changed = False
    for line in lines:
        if _looks_like_annotation_row(line):
            stripped_lines.append(line.split("\t", 1)[0].strip())
            changed = True
        else:
            stripped_lines.append(line)

    return "\n".join(stripped_lines) if changed else text


def _looks_like_annotation_row(line: str) -> bool:
    parts = [part.strip() for part in line.split("\t")]
    if len(parts) not in {2, 3} or not parts[0]:
        return False

    label = parts[-1]
    if not label or any(char.isspace() for char in label):
        return False

    return label[0].isupper() and all(char.isalnum() or char == "_" for char in label)


def _sorted_counts(counts: Counter[str]) -> list[tuple[str, int]]:
    return sorted(counts.items(), key=lambda item: (-item[1], item[0].casefold()))


def _count_percent_rows(counts: Counter[str], total: int) -> list[tuple[str, ...]]:
    return [(name, str(count), _percent(count, total)) for name, count in _sorted_counts(counts)]


def _percent(value: int | float, total: int | float) -> str:
    if not total:
        return "0.0%"
    return f"{(float(value) / float(total)) * 100:.1f}%"


def _ratio(value: int, total: int) -> str:
    if not total:
        return "0.000"
    return f"{value / total:.3f}"


def _mean(values: list[int]) -> str:
    if not values:
        return "0.0"
    return f"{sum(values) / len(values):.1f}"
