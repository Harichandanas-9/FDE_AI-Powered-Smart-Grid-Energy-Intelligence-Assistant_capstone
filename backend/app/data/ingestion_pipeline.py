"""
End-to-end ingestion pipeline.

Reads every known CSV in DATA_DIR, normalizes, cleans, aggregates, and writes
NDJSON chunks (one chunk per line) to {processed_dir}/chunks.jsonl.

STEP 4 (embeddings + ChromaDB) consumes this file. This separation lets us:
  - re-run embedding without re-parsing CSVs,
  - eyeball the produced chunks via `head chunks.jsonl`,
  - unit-test the ingestion in isolation.
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

import pandas as pd

from app.core.config import get_settings
from app.core.logging import get_logger
from app.data.aggregator import aggregate
from app.data.cleaner import clean
from app.data.loader import discover_datasets, load_csv
from app.data.normalizer import normalize
from app.data.templater import chunk_to_dict, render_dataframe

logger = get_logger(__name__)

# Sensible defaults — tuned so the 130 MB household / electric CSVs complete
# inside an HTTP request timeout (under ~60 s). Increase max_rows via the
# request body if you need broader data; the pipeline tolerates any size.
DEFAULT_MAX_ROWS = {
    "stability":   100,       # 100 rows -> ~15s ETL (enough for all charts)
    "household":   100,       # demo limit
    "consumption": 100,       # demo limit
}


@dataclass
class IngestionReport:
    started_at: float
    finished_at: float = 0.0
    chunks_written: int = 0
    per_source: dict = field(default_factory=dict)
    output_path: str = ""
    errors: List[str] = field(default_factory=list)

    @property
    def duration_seconds(self) -> float:
        return max(0.0, self.finished_at - self.started_at)

    def to_dict(self) -> dict:
        return {
            "duration_seconds": round(self.duration_seconds, 2),
            "chunks_written": self.chunks_written,
            "per_source": self.per_source,
            "output_path": self.output_path,
            "errors": self.errors,
        }


def run_ingestion(
    data_dir: Optional[Path] = None,
    processed_dir: Optional[Path] = None,
    *,
    sources: Optional[List[str]] = None,
    max_rows_override: Optional[dict] = None,
    tenant_id: str = "default",
) -> IngestionReport:
    """
    Run the full pipeline.

    Parameters
    ----------
    data_dir : Path
        Folder containing the raw CSVs (defaults to settings.data_dir).
    processed_dir : Path
        Folder to write chunks.jsonl into (defaults to ./data_processed).
    sources : list of source keys
        Filter — e.g. ['stability'] to only ingest one dataset.
    max_rows_override : dict
        Map source_key -> max_rows for unit tests / quick demos.
    """
    from app.utils.paths import resolve_dir
    settings = get_settings()
    # Use the smart resolver so it works whether uvicorn was launched from
    # project root or from inside backend/.
    data_dir = Path(data_dir) if data_dir else resolve_dir(settings.data_dir, create=True)
    processed_dir = Path(processed_dir) if processed_dir else resolve_dir("./data_processed", create=True)
    out_path = processed_dir / "chunks.jsonl"

    report = IngestionReport(started_at=time.time(), output_path=str(out_path))
    logger.info("ingest_start",
                extra={"data_dir": str(data_dir.resolve()),
                       "processed_dir": str(processed_dir.resolve())})
    found = discover_datasets(data_dir)
    if not found:
        msg = (f"No known datasets found in {data_dir.resolve()}. "
               f"Place CSVs there (allowed names: smart_grid_stability_augmented.csv, "
               f"household_power_consumption.csv, electric_power_consumption.csv).")
        logger.error("no_datasets", extra={"data_dir": str(data_dir.resolve())})
        report.errors.append(msg)
        report.finished_at = time.time()
        return report

    max_rows = {**DEFAULT_MAX_ROWS, **(max_rows_override or {})}
    written = 0
    with out_path.open("w", encoding="utf-8") as out_fh:
        for path, key in found:
            if sources and key not in sources:
                continue
            try:
                logger.info("ingest_source_begin", extra={"source": key,
                                                           "file": path.name})
                df_raw = load_csv(path, max_rows=max_rows.get(key))
                if isinstance(df_raw, pd.DataFrame):
                    df_norm = normalize(df_raw, key)
                    df_clean = clean(df_norm)
                    df_agg = aggregate(df_clean)
                    df_chunks = render_dataframe(df_agg)
                    n = 0
                    for _, row in df_chunks.iterrows():
                        out_fh.write(json.dumps(chunk_to_dict(row, tenant_id=tenant_id),
                                                default=str))
                        out_fh.write("\n")
                        n += 1
                    report.per_source[key] = n
                    written += n
                    logger.info(
                        "ingest_source_done",
                        extra={"source": key, "chunks": n},
                    )
            except Exception as exc:  # noqa: BLE001
                msg = f"{key}: {exc.__class__.__name__}: {exc}"
                logger.exception("ingest_source_failed", extra={"source": key})
                report.errors.append(msg)

    report.chunks_written = written
    report.finished_at = time.time()
    logger.info("ingest_complete", extra=report.to_dict())
    return report
