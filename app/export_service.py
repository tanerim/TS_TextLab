"""UTF-8, tab-delimited CSV exports for NLP workflows."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Iterable, Sequence


def timestamped_csv_path(path: str, timestamp: str) -> Path:
    target = Path(path)
    if target.suffix.lower() == ".csv":
        target = target.with_suffix("")
    name = target.name
    if not name.endswith(f"-{timestamp}"):
        name = f"{name}-{timestamp}"
    return target.with_name(f"{name}.csv")


def write_tab_csv(path: Path, headers: Sequence[str], rows: Iterable[Sequence[str]]) -> None:
    # csv.writer preserves literal tabs, quotes and multiline tokens by quoting fields.
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream, delimiter="\t", lineterminator="\n")
        writer.writerow(headers)
        writer.writerows(rows)
