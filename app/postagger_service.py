"""Local spaCy TS PosTagger integration."""

from __future__ import annotations

import logging

from app.errors import DependencyUnavailableError, EmptyInputError, TextLabError
from app.resource_manager import resolve_model_dir

logger = logging.getLogger(__name__)


class PosTaggerService:
    """Loads the local spaCy model once and keeps it in memory."""

    def __init__(self) -> None:
        self._nlp = None

    def tag(self, text: str) -> list[tuple[str, str]]:
        cleaned = text.strip()
        if not cleaned:
            raise EmptyInputError("Lütfen işlenecek bir metin girin.")

        nlp = self._load_model()
        try:
            doc = nlp(cleaned)
        except Exception as exc:  # pragma: no cover - external library guard
            raise TextLabError(f"POS tagging sırasında hata oluştu: {exc}") from exc

        return [(token.text, token.tag_ or token.pos_ or "-") for token in doc]

    def tag_tokens(self, tokens: list[str]) -> list[tuple[str, str]]:
        if not tokens:
            raise EmptyInputError("Lütfen işlenecek bir metin girin.")

        nlp = self._load_model()
        try:
            from spacy.tokens import Doc

            doc = Doc(nlp.vocab, words=tokens)
            for _, component in nlp.pipeline:
                doc = component(doc)
        except Exception as exc:  # pragma: no cover - external library guard
            raise TextLabError(f"POS tagging sırasında hata oluştu: {exc}") from exc

        return [(token.text, token.tag_ or token.pos_ or "-") for token in doc]

    def _load_model(self):
        if self._nlp is not None:
            return self._nlp

        try:
            import spacy
        except ImportError as exc:
            raise DependencyUnavailableError(
                "`spacy` kurulu değil. Geliştirme ortamında `pip install -r requirements.txt` çalıştırın."
            ) from exc

        model_dir = resolve_model_dir()
        logger.info("Loading TS PosTagger model from %s", model_dir)
        try:
            self._nlp = spacy.load(model_dir)
        except Exception as exc:
            raise TextLabError(f"TS PosTagger modeli yüklenemedi: {exc}") from exc

        return self._nlp
