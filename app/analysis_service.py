"""Shared token-based analysis helpers."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from statistics import median

from app.postagger_service import PosTaggerService
from app.tokenizer_service import FrequencyCaseMode, TokenizerMode, TokenizerService


LEXICAL_TAGS = frozenset({"", "Valid_Word", "OOV", "One_Char_Fixed"})
SOCIAL_TAGS = frozenset({"Mention", "Hashtag", "URL", "Emoji", "Email", "Date", "Time"})
PUNCTUATION_CHARS = frozenset(".!?;:,-()[]{}\"'`…")
LEXICAL_POS = frozenset({"NOUN", "VERB", "ADJ", "ADV"})
FUNCTION_POS = frozenset({"ADP", "CCONJ", "SCONJ", "DET", "PRON", "PART"})


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
        tagged = self.tokenizer_service.tokenize(text, "tagged_lines")
        pairs = [(row[0], row[1] if len(row) > 1 else "") for row in tagged.rows if row and row[0].strip()]
        pos_by_position: list[str] = ["-"] * len(pairs)
        if include_pos:
            pos_rows = self.postagger_service.tag_tagged_tokens(pairs)
            pos_by_position = [pos for _, pos in pos_rows]

        paragraph_sequence = self._paragraph_sequence(text)
        tokens: list[TokenInfo] = []
        for position, ((surface, tokenizer_tag), pos) in enumerate(zip(pairs, pos_by_position, strict=True), start=1):
            tag = normalize_tokenizer_tag(surface, tokenizer_tag)
            paragraph = paragraph_sequence[position - 1] if position - 1 < len(paragraph_sequence) else 1
            tokens.append(TokenInfo(surface=surface, position=position, tokenizer=tag, pos=pos, paragraph=paragraph))
        return AnalysisDocument(tokens=tokens)

    def add_pos(self, document: AnalysisDocument) -> AnalysisDocument:
        pairs = [(token.surface, token.tokenizer) for token in document.tokens]
        pos_rows = self.postagger_service.tag_tagged_tokens(pairs)
        tokens = [
            TokenInfo(
                surface=token.surface,
                position=token.position,
                tokenizer=token.tokenizer,
                pos=pos,
                paragraph=token.paragraph,
            )
            for token, (_, pos) in zip(document.tokens, pos_rows, strict=True)
        ]
        return AnalysisDocument(tokens=tokens)

    @staticmethod
    def has_pos(document: AnalysisDocument) -> bool:
        return any(token.pos and token.pos != "-" for token in document.tokens)

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


def pos_rows(document: AnalysisDocument) -> tuple[list[str], list[tuple[str, ...]], str]:
    rows = [(token.surface, token.pos) for token in document.tokens]
    return ["Token", "POS"], rows, "\n".join("\t".join(row) for row in rows)


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


def token_statistics_rows(text: str, document: AnalysisDocument) -> tuple[list[str], list[tuple[str, ...]], str]:
    lexical = document.lexical_tokens
    paragraph_lengths = [len([token for token in paragraph if is_lexical(token)]) for paragraph in document.paragraphs]
    token_lengths = [token.length for token in lexical]
    rows = [
        ("Characters", str(len(text)), "Total Unicode code points in the input text."),
        ("Tokens", str(len(document.tokens)), "All non-empty TS Tokenizer tokens."),
        ("Lexical tokens", str(len(lexical)), "Word-like tokens used for lexical calculations."),
        ("Unique tokens", str(len({token.surface.casefold() for token in lexical})), "Distinct lexical forms after case folding."),
        ("Sentences", str(len(document.paragraphs)), "Line-based units; each non-empty input line is counted as one unit."),
        ("Punctuation", str(sum(1 for token in document.tokens if is_punctuation(token))), "Tokens classified or detected as punctuation."),
        ("Type-token ratio", _ratio(len({token.surface.casefold() for token in lexical}), len(lexical)), "Unique lexical tokens divided by lexical tokens."),
        ("Mean token length", _mean(token_lengths), "Average character length of lexical tokens."),
        ("Mean sentence length", _mean(paragraph_lengths), "Average lexical tokens per non-empty line."),
    ]
    return ["Measure", "Value", "Description"], rows, "\n".join("\t".join(row) for row in rows)


def token_composition_rows(document: AnalysisDocument) -> tuple[list[str], list[tuple[str, ...]], str]:
    counts = Counter(token.tokenizer for token in document.tokens)
    rows = _count_percent_rows(counts, len(document.tokens))
    return ["Category", "Count", "Percentage"], rows, "\n".join("\t".join(row) for row in rows)


def pos_distribution_rows(document: AnalysisDocument) -> tuple[list[str], list[tuple[str, ...]], str]:
    lexical = document.lexical_tokens
    counts = Counter(token.pos for token in document.tokens if token.pos and token.pos != "-")
    lexical_words = sum(1 for token in lexical if token.pos in LEXICAL_POS)
    function_words = sum(1 for token in lexical if token.pos in FUNCTION_POS)
    rows = [(name, str(count), _percent(count, max(1, sum(counts.values()))), "POS distribution") for name, count in _sorted_counts(counts)]
    rows.extend(
        [
            ("", str(lexical_words), _percent(lexical_words, len(lexical)), "Lexical Density"),
            ("", str(lexical_words), _percent(lexical_words, len(lexical)), "Lexical Words"),
            ("", str(function_words), _percent(function_words, len(lexical)), "Function Words"),
        ]
    )
    return ["POS", "Count", "Percentage", "Info"], rows, "\n".join("\t".join(row) for row in rows)


def text_profile_rows(document: AnalysisDocument) -> tuple[list[str], list[tuple[str, ...]], str]:
    paragraph_lengths = [len([token for token in paragraph if is_lexical(token)]) for paragraph in document.paragraphs]
    punctuation_count = sum(1 for token in document.tokens if is_punctuation(token))
    lexical_count = len(document.lexical_tokens)
    rows = [
        ("Paragraph count", str(len(document.paragraphs)), _percent(len(document.paragraphs), len(document.paragraphs))),
        ("Mean paragraph length", _mean(paragraph_lengths), _percent(round(float(_mean(paragraph_lengths))), max(paragraph_lengths or [1]))),
        ("Median paragraph length", _format_number(median(paragraph_lengths) if paragraph_lengths else 0), _percent(round(median(paragraph_lengths) if paragraph_lengths else 0), max(paragraph_lengths or [1]))),
        ("Shortest paragraph", str(min(paragraph_lengths or [0])), _percent(min(paragraph_lengths or [0]), max(paragraph_lengths or [1]))),
        ("Longest paragraph", str(max(paragraph_lengths or [0])), _percent(max(paragraph_lengths or [0]), max(paragraph_lengths or [1]))),
        ("Punctuation density", str(punctuation_count), _percent(punctuation_count, len(document.tokens))),
        ("Lexical density", str(lexical_count), _percent(lexical_count, len(document.tokens))),
    ]
    length_counts = Counter(paragraph_lengths)
    for length, count in sorted(length_counts.items()):
        rows.append((f"{length} tokens", str(count), _percent(count, len(document.paragraphs))))
    return ["Measure", "Value", "Distribution"], rows, "\n".join("\t".join(row) for row in rows)


def social_profile_rows(document: AnalysisDocument) -> tuple[list[str], list[tuple[str, ...]], str]:
    categories = ["Mention", "Hashtag", "URL", "Emoji", "Email", "Date", "Time"]
    counts = Counter(token.tokenizer for token in document.tokens)
    rows = [(category, str(counts.get(category, 0)), _percent(counts.get(category, 0), len(document.tokens))) for category in categories]
    return ["Category", "Count", "Percentage"], rows, "\n".join("\t".join(row) for row in rows)


def lexical_coverage_rows(document: AnalysisDocument) -> tuple[list[str], list[tuple[str, ...]], str]:
    lexical = document.lexical_tokens
    oov = [token for token in lexical if token.tokenizer == "OOV"]
    recognized = max(0, len(lexical) - len(oov))
    rows = [
        ("Recognized lexical forms", str(recognized), _percent(recognized, len(lexical))),
        ("OOV", str(len(oov)), _percent(len(oov), len(lexical))),
    ]
    return ["Category", "Count", "Percentage"], rows, "\n".join("\t".join(row) for row in rows)


def oov_frequency_rows(document: AnalysisDocument) -> tuple[list[str], list[tuple[str, ...]], str]:
    counts = Counter(token.surface for token in document.lexical_tokens if token.tokenizer == "OOV")
    rows = [(str(count), token) for token, count in _sorted_counts(counts)]
    return ["Frequency", "Token"], rows, "\n".join("\t".join(row) for row in rows)


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
    if is_lexical(token):
        return "Words"
    if token.tokenizer == "Punctuation":
        return "Punctuation"
    if token.tokenizer == "URL":
        return "URLs"
    if token.tokenizer == "Mention":
        return "Mentions"
    if token.tokenizer == "Hashtag":
        return "Hashtags"
    return "Other"


def is_lexical(token: TokenInfo) -> bool:
    return token.tokenizer in LEXICAL_TAGS and any(char.isalnum() for char in token.surface)


def is_punctuation(token: TokenInfo) -> bool:
    return token.tokenizer == "Punctuation" or all(char in PUNCTUATION_CHARS for char in token.surface)


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


def _format_number(value: float | int) -> str:
    if float(value).is_integer():
        return str(int(value))
    return f"{value:.1f}"
