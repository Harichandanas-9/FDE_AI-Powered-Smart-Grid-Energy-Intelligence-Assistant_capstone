"""
CSV loader.

Handles the three capstone datasets:
  1. smart_grid_stability_augmented.csv  (comma-delimited)
  2. household_power_consumption.csv     (semicolon-delimited, '?' = NaN)
  3. electric_power_consumption.csv      (semicolon- or comma-delimited mirror)

Design notes
------------
- Auto-detects delimiter by sampling the file header.
- Supports chunked reads for the 2M-row household file so memory stays bounded.
- Treats UCI's '?' string as NaN.
- Never silently fails: if a file is missing we raise FileNotFoundError early.
"""
from __future__ import annotations

import csv
from pathlib import Path
from typing import Iterator, Optional

import pandas as pd

from app.core.logging import get_logger

logger = get_logger(__name__)

DATASET_SOURCES = {
    "smart_grid_stability_augmented.csv": "stability",
    "household_power_consumption.csv": "household",
    "electric_power_consumption.csv": "consumption",
}


def _sniff_delimiter(path: Path) -> str:
    with path.open("r", encoding="utf-8", errors="replace") as f:
        sample = f.read(8192)
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=[",", ";", "\t"])
        return dialect.delimiter
    except csv.Error:
        first_line = sample.splitlines()[0] if sample else ""
        return ";" if first_line.count(";") > first_line.count(",") else ","


def load_csv(
    path: Path,
    *,
    chunksize: Optional[int] = None,
    max_rows: Optional[int] = None,
) -> "pd.DataFrame | Iterator[pd.DataFrame]":
    if not path.exists():
        raise FileNotFoundError(f"Dataset not found: {path}")

    delim = _sniff_delimiter(path)
    logger.info(
        "csv_load_begin",
        extra={"path": str(path), "delimiter": delim, "chunksize": chunksize},
    )

    engine = "python" if delim == ";" else "c"
    kwargs = dict(
        sep=delim,
        na_values=["?", "", "NA", "N/A", "null"],
        keep_default_na=True,
        nrows=max_rows,
        on_bad_lines="skip",
        encoding="utf-8",
        engine=engine,
    )
    if engine == "c":
        kwargs["low_memory"] = False

    if chunksize:
        return pd.read_csv(path, chunksize=chunksize, **kwargs)
    df = pd.read_csv(path, **kwargs)
    logger.info(
        "csv_load_done",
        extra={"path": str(path), "rows": len(df), "cols": len(df.columns)},
    )
    return df


def source_for(path: Path) -> str:
    return DATASET_SOURCES.get(path.name, "unknown")


def discover_datasets(data_dir: Path) -> list[tuple[Path, str]]:
    out: list[tuple[Path, str]] = []
    if not data_dir.exists():
        logger.warning("data_dir_missing", extra={"data_dir": str(data_dir)})
        return out
    for child in data_dir.iterdir():
        if not child.is_file():
            continue
        if child.suffix.lower() not in (".csv", ".txt"):
            continue
        key = DATASET_SOURCES.get(child.name)
        if key is None:
            logger.warning("dataset_skipped_unknown", extra={"file": child.name})
            continue
        out.append((child, key))
    return out
