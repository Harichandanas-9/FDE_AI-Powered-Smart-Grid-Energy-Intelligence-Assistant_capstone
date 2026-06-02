"""
Cleaner — runs AFTER normalization, BEFORE aggregation.

Responsibilities:
  - drop rows with too many NaNs across numeric fields
  - clip numeric outliers to a sane physical range
  - coerce dtypes deterministically

Why we don't impute aggressively:
  Imputing voltage/current values risks hiding the very anomalies the system is
  trying to detect. We prefer to drop unreliable rows than fabricate signal.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from app.core.logging import get_logger

logger = get_logger(__name__)

# Physically plausible ranges. Anything outside is clipped (not dropped) so
# extreme but interesting events remain visible at the boundary.
PHYSICAL_RANGES = {
    "voltage":           (50.0,   500.0),
    "current":           (0.0,   100.0),
    "power_consumption": (0.0,   1000.0),
    "demand_load":       (0.0,   1000.0),
    "grid_frequency":    (40.0,   60.0),
    "stability_score":   (-1.0,    1.0),
}

# A row must have at least this fraction of numeric fields populated to survive.
MIN_NUMERIC_COVERAGE = 0.5


def clean(df: pd.DataFrame) -> pd.DataFrame:
    """Clean a normalized DataFrame in place-safe fashion. Returns new df."""
    if df.empty:
        return df

    df = df.copy()
    before = len(df)

    # 1) Drop rows where the timestamp couldn't be parsed
    df = df.dropna(subset=["timestamp"])

    # 2) Coerce numeric columns
    num_cols = list(PHYSICAL_RANGES.keys())
    for c in num_cols:
        df[c] = pd.to_numeric(df[c], errors="coerce")

    # 3) Drop rows that are mostly NaN across numeric fields
    cov = df[num_cols].notna().sum(axis=1) / len(num_cols)
    df = df[cov >= MIN_NUMERIC_COVERAGE]

    # 4) Clip outliers to physical ranges (preserve direction of anomaly)
    for c, (lo, hi) in PHYSICAL_RANGES.items():
        df[c] = df[c].clip(lower=lo, upper=hi)

    # 5) Final dtype tidy
    df["outage_event"] = df["outage_event"].fillna(0).astype(int)
    df["transformer_status"] = df["transformer_status"].fillna("unknown").astype(str)
    df["region"] = df["region"].fillna("Unknown Zone").astype(str)
    df["equipment_type"] = df["equipment_type"].fillna("unknown").astype(str)

    logger.info(
        "cleaned",
        extra={"rows_before": before, "rows_after": len(df),
               "dropped": before - len(df)},
    )
    return df.reset_index(drop=True)
