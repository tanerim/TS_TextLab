"""Run NLP services without launching the GUI."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.logging_config import configure_logging
from app.postagger_service import PosTaggerService
from app.tokenizer_service import TokenizerService


def main() -> int:
    configure_logging()
    sample = "Ali bugün İstanbul'a gitti."

    tokens = TokenizerService().tokenize(sample)
    print("TOKENS")
    for row in tokens.rows:
        print("\t".join(row))

    print("\nPOS")
    for token, tag in PosTaggerService().tag(sample):
        print(f"{token}\t{tag}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
