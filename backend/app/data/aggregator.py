"""
Aggregator — groups cleaned rows into INCIDENT WINDOWS.

Each incident is a (region, time_window, equipment_type) bucket. The aggregator
condenses many raw rows into a single record with:
  - summary statistics (mean voltage, max demand, std frequency, ...)
  - a severity classification (low | medium | high | critical)
  - an outage flag if ANY row in the window flagged an outage

Windowing strategy
------------------
  stability source  : already 1 row = 1 incident — pass through (group of 1)
  household / consumption : hourly windows, so 2M minute-rows -> ~35K incidents

This is the layer that controls the eventual chunk count in the vector store.
"""
from __future__ import annotations

import pandas as pd

from app.core.logging import get_logger

logger = get_logger(__name__)


def _severity(row: pd.Series) -> str:
    """
    Classify severity using a small rule book on the aggregated row.

    The numeric thresholds are sized so that *most* rows fall into low/medium
    and the tail goes high/critical, giving a useful demo distribution.
    """
    v_dev = abs(row["voltage_mean"] - 230.0) / 230.0
    f_dev = abs(row["frequency_mean"] - 50.0)
    stab = row["stability_score_mean"]
    has_outage = row["outage_count"] > 0

    if has_outage or v_dev > 0.12 or f_dev > 1.5 or stab < -0.5:
        return "critical"
    if v_dev > 0.07 or f_dev > 0.8 or stab < -0.1:
        return "high"
    if v_dev > 0.03 or f_dev > 0.3 or stab < 0.3:
        return "medium"
    return "low"


def aggregate(df: pd.DataFrame, *, freq: str = "1h") -> pd.DataFrame:
    """
    Aggregate cleaned df into incident windows.

    Parameters
    ----------
    df : DataFrame from cleaner.clean()
    freq : pandas offset alias for the window size. '1h' by default.
           Stability data is treated as already-aggregated and bypassed.
    """
    if df.empty:
        return df

    source = df["source_dataset"].iloc[0] if "source_dataset" in df.columns else "unknown"

    if source == "stability":
        # Each row is already one incident snapshot. Synthesize aggregation
        # columns so downstream code has a uniform schema.
        out = df.rename(columns={
            "voltage": "voltage_mean",
            "current": "current_mean",
            "power_consumption": "power_mean",
            "demand_load": "demand_max",
            "grid_frequency": "frequency_mean",
            "stability_score": "stability_score_mean",
        }).copy()
        out["voltage_std"] = 0.0
        out["frequency_std"] = 0.0
        out["outage_count"] = out["outage_event"].astype(int)
        out["row_count"] = 1
        out["window_start"] = out["timestamp"]
        out["window_end"] = out["timestamp"]
    else:
        # Hourly windowed aggregation
        df = df.sort_values("timestamp").copy()
        df["_window"] = df["timestamp"].dt.floor(freq)
        grouped = df.groupby(["_window", "region", "equipment_type",
                              "source_dataset"], as_index=False)
        out = grouped.agg(
            voltage_mean=("voltage", "mean"),
            voltage_std=("voltage", "std"),
            current_mean=("current", "mean"),
            power_mean=("power_consumption", "mean"),
            demand_max=("demand_load", "max"),
            frequency_mean=("grid_frequency", "mean"),
            frequency_std=("grid_frequency", "std"),
            stability_score_mean=("stability_score", "mean"),
            outage_count=("outage_event", "sum"),
            row_count=("voltage", "size"),
        )
        out["window_start"] = out["_window"]
        out["window_end"] = out["_window"] + pd.tseries.frequencies.to_offset(freq)
        out["timestamp"] = out["_window"]
        out["transformer_status"] = out["voltage_mean"].apply(
            lambda v: "stable" if abs(v - 230) / 230 < 0.03
            else ("warning" if abs(v - 230) / 230 < 0.08 else "overload_risk")
        )
        out["outage_event"] = (out["outage_count"] > 0).astype(int)
        out = out.drop(columns=["_window"])

    # Fill any NaN std with 0 (single-sample windows)
    for c in ("voltage_std", "frequency_std"):
        if c in out.columns:
            out[c] = out[c].fillna(0.0)

    # Severity tag
    out["severity"] = out.apply(_severity, axis=1)

    # Compact incident_id for citation
    out["incident_id"] = (
        out["source_dataset"].astype(str)
        + "-"
        + out["region"].str.replace(" ", "_")
        + "-"
        + out["window_start"].dt.strftime("%Y%m%d%H%M")
    )

    logger.info(
        "aggregated",
        extra={
            "source": source,
            "incidents": len(out),
            "severity_counts": out["severity"].value_counts().to_dict(),
        },
    )
    return out
