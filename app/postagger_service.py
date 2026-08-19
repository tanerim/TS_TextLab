"""TS POSTagger package integration."""

from __future__ import annotations

import logging

from app.errors import DependencyUnavailableError, EmptyInputError, TextLabError

logger = logging.getLogger(__name__)


MODEL_TAGGED_TOKENIZER_TAGS = frozenset({"Apostrophed", "OOV", "One_Char_Fixed", "Valid_Word"})


class PosTaggerService:
    """Thin adapter around the external ts-postagger package."""

    def __init__(self) -> None:
        self._pos = None
        self._predictor = None
        self._resolve_tag = None

    def tag(self, text: str) -> list[tuple[str, str]]:
        cleaned = text.strip()
        if not cleaned:
            raise EmptyInputError("Lütfen işlenecek bir metin girin.")

        pos = self._load_pos_function()
        try:
            tokens = pos(cleaned)
        except Exception as exc:  # pragma: no cover - external library guard
            raise TextLabError(f"POS tagging sırasında hata oluştu: {exc}") from exc

        return [(token.text, token.pos or "-") for token in tokens]

    def tag_tagged_tokens(self, tagged_tokens: list[tuple[str, str]]) -> list[tuple[str, str]]:
        if not tagged_tokens:
            raise EmptyInputError("Lütfen işlenecek bir metin girin.")

        tokens = [token for token, _ in tagged_tokens]
        tagged_by_model = self.tag_tokens(tokens)
        rows: list[tuple[str, str]] = []
        for (token, tokenizer_tag), (_, model_tag) in zip(tagged_tokens, tagged_by_model, strict=True):
            rows.append((token, self._select_tag(token, tokenizer_tag, model_tag)))
        return rows

    def tag_tokens(self, tokens: list[str]) -> list[tuple[str, str]]:
        if not tokens:
            raise EmptyInputError("Lütfen işlenecek bir metin girin.")

        predictor = self._load_predictor()
        try:
            predicted_tags = predictor.predict(tokens)
        except Exception as exc:  # pragma: no cover - external library guard
            raise TextLabError(f"POS tagging sırasında hata oluştu: {exc}") from exc

        if len(predicted_tags) != len(tokens):
            raise TextLabError(
                "POS tagging sırasında token hizalama hatası oluştu: "
                f"{len(tokens)} token için {len(predicted_tags)} etiket döndü."
            )

        return list(zip(tokens, predicted_tags, strict=True))

    def _select_tag(self, token: str, tokenizer_tag: str | None, model_tag: str) -> str:
        resolve_tag = self._load_resolver()
        tag = (tokenizer_tag or "").strip()

        if not tag:
            tag = PosTaggerService._social_token_tag(token) or "Valid_Word"

        if tag in MODEL_TAGGED_TOKENIZER_TAGS:
            return resolve_tag(token_type=tag, predicted_pos=model_tag) or model_tag

        return resolve_tag(token_type=tag, predicted_pos=model_tag) or tag

    @staticmethod
    def _social_token_tag(token: str) -> str | None:
        if len(token) < 2:
            return None

        marker = token[0]
        if marker not in {"#", "@"}:
            return None

        body = token[1:]
        if not any(char.isalnum() for char in body):
            return None
        if any(char.isspace() for char in body):
            return None

        return "Hashtag" if marker == "#" else "Mention"

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

    def _load_predictor(self):
        if self._predictor is not None:
            return self._predictor

        try:
            from ts_postagger.api import _get_predictor
        except ImportError as exc:
            raise DependencyUnavailableError(
                "`ts-postagger` kurulu değil. Geliştirme ortamında `pip install -r requirements.txt` çalıştırın."
            ) from exc

        logger.info("Loading TS POSTagger package predictor")
        try:
            self._predictor = _get_predictor()
        except Exception as exc:
            raise TextLabError(f"TS POSTagger modeli yüklenemedi: {exc}") from exc

        return self._predictor

    def _load_resolver(self):
        if self._resolve_tag is not None:
            return self._resolve_tag

        try:
            from ts_postagger.resolver import resolve_tag
        except ImportError as exc:
            raise DependencyUnavailableError(
                "`ts-postagger` kurulu değil. Geliştirme ortamında `pip install -r requirements.txt` çalıştırın."
            ) from exc

        self._resolve_tag = resolve_tag
        return self._resolve_tag
