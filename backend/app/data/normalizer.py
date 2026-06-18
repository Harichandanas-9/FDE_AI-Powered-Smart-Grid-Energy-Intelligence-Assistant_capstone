"""
Schema normalizer.

Maps each source dataset's columns to the COMMON SMART GRID SCHEMA defined in
the capstone requirements:

    voltage, current, power_consumption, transformer_status, outage_event,
    region, demand_load, timestamp, grid_frequency, equipment_type

Where a source doesn't natively carry a field (e.g. stability data has no
real timestamp), we synthesize a plausible value and record the synthesis
strategy in the metadata so it is transparent during evaluation.
"""
from __future__ import annotations

import hashlib
from datetime import datetime, timedelta

import numpy as np
import pandas as pd

from app.core.logging import get_logger

logger = get_logger(__name__)

COMMON_COLUMNS = [
    "timestamp",
    "region",
    "equipment_type",
    "voltage",
    "current",
    "power_consumption",
    "demand_load",
    "grid_frequency",
    "transformer_status",
    "outage_event",
    "stability_score",
    "source_dataset",
]

# Synthetic regions used to make region-wise heatmaps meaningful.
REGIONS = ["North Zone", "South Zone", "East Zone", "West Zone", "Central Hub"]

# Baseline grid frequency (Hz) used as the centre point for synthesized values.
_NOMINAL_FREQ = 50.0
_NOMINAL_VOLTAGE = 230.0


def _stable_region(seed: str) -> str:
    """Deterministically pick a region from a string seed."""
    idx = int(hashlib.md5(seed.encode()).hexdigest(), 16) % len(REGIONS)
    return REGIONS[idx]


def _classify_transformer(stability: float) -> str:
    """Map a raw stability value to a transformer status label.

    Negative stab = stable; small positive = warning; larger positive = overload_risk.
    """
    if stability < 0:
        return "stable"
    if stability < 0.03:
        return "warning"
    return "overload_risk"


# ----------------------------- stability -------------------------------- #
def normalize_stability(df: pd.DataFrame) -> pd.DataFrame:
    """
    Smart Grid Stability dataset (Kaggle: pcbreviglieri/smart-grid-stability).

    Source columns: tau1..tau4, p1..p4, g1..g4, stab, stabf
        - tau* : reaction times (s)
        - p*   : net power produced/consumed at four nodes (kW)
        - g*   : price-elasticity coefficients
        - stab : real-valued stability characteristic (negative = stable)
        - stabf: 'stable' / 'unstable'

    Strategy:
        - power_consumption = sum of consumer powers (|p2| + |p3| + |p4|)
        - demand_load       = power_consumption (same view; expressed in kW)
        - voltage           = nominal 230 V perturbed by stab
        - current           = power_consumption / voltage (W = V * I)
        - grid_frequency    = 50 Hz +/- proportional to stab
        - transformer_status= derived from stab
        - outage_event      = 1 if stabf == 'unstable'
        - timestamp         = synthesized 1-minute increments from 2024-01-01
        - region            = hash(row_id) -> deterministic spread across regions
        - equipment_type    = 'grid_node'
    """
    df = df.copy()
    n = len(df)
    start = datetime(2024, 1, 1, 0, 0, 0)
    df["timestamp"] = [start + timedelta(minutes=i) for i in range(n)]

    consumer_p = (df.get("p2", 0).abs()
                  + df.get("p3", 0).abs()
                  + df.get("p4", 0).abs())
    df["power_consumption"] = consumer_p.astype(float)
    df["demand_load"] = consumer_p.astype(float)
    df["voltage"] = _NOMINAL_VOLTAGE + df["stab"].fillna(0) * 50.0
    df["current"] = (df["power_consumption"] * 1000.0
                     / df["voltage"].replace(0, np.nan)).fillna(0)
    df["grid_frequency"] = _NOMINAL_FREQ - df["stab"].fillna(0) * 5.0
    df["transformer_status"] = df["stab"].fillna(0).apply(_classify_transformer)
    df["outage_event"] = (df.get("stabf", "stable").astype(str)
                          .str.lower().eq("unstable").astype(int))
    df["stability_score"] = (-df["stab"].fillna(0)).clip(-1, 1)  # +ve = stable
    df["region"] = [_stable_region(f"stability-{i}") for i in range(n)]
    df["equipment_type"] = "grid_node"
    df["source_dataset"] = "stability"
    return df[COMMON_COLUMNS]


# ----------------------------- household / consumption ------------------ #
def normalize_household(df: pd.DataFrame, source_key: str) -> pd.DataFrame:
    """
    UCI household + Kaggle electric power consumption mirror.

    Source columns: Date, Time, Global_active_power, Global_reactive_power,
                    Voltage, Global_intensity, Sub_metering_1..3

    Strategy:
        - voltage              = Voltage
        - current              = Global_intensity (A)
        - power_consumption    = Global_active_power (kW)
        - demand_load          = Global_active_power + Global_reactive_power
        - grid_frequency       = 50 Hz +/- noise proportional to voltage deviation
        - transformer_status   = derived from voltage deviation
        - outage_event         = 1 where Global_active_power == 0 or NaN
        - timestamp            = Date + Time combined
        - region               = hash(date_day) -> stable per-day region binding
        - equipment_type       = 'smart_meter'
    """
    df = df.copy()

    # Combine date + time -> timestamp
    if "Date" in df.columns and "Time" in df.columns:
        df["timestamp"] = pd.to_datetime(
            df["Date"].astype(str) + " " + df["Time"].astype(str),
            format="%d/%m/%Y %H:%M:%S",
            errors="coerce",
        )
    else:
        # Fallback: synthesize 1-minute increments
        df["timestamp"] = pd.date_range(
            "2007-01-01", periods=len(df), freq="1min"
        )

    df["voltage"] = pd.to_numeric(df.get("Voltage"), errors="coerce")
    df["current"] = pd.to_numeric(df.get("Global_intensity"), errors="coerce")
    df["power_consumption"] = pd.to_numeric(
        df.get("Global_active_power"), errors="coerce"
    )
    reactive = pd.to_numeric(df.get("Global_reactive_power", 0), errors="coerce").fillna(0)
    df["demand_load"] = df["power_consumption"].fillna(0) + reactive

    # Synthesize grid frequency from voltage deviation (proxy)
    v_dev = (df["voltage"] - _NOMINAL_VOLTAGE) / _NOMINAL_VOLTAGE
    df["grid_frequency"] = _NOMINAL_FREQ - v_dev.fillna(0) * 5.0

    # Transformer status from voltage deviation
    def _status_from_v(v: float) -> str:
        if pd.isna(v):
            return "unknown"
        dev = abs(v - _NOMINAL_VOLTAGE) / _NOMINAL_VOLTAGE
        if dev < 0.03:
            return "stable"
        if dev < 0.08:
            return "warning"
        return "overload_risk"

    df["transformer_status"] = df["voltage"].apply(_status_from_v)

    # Outage marker: zero/NaN active power
    df["outage_event"] = (
        (df["power_consumption"].isna()) | (df["power_consumption"] == 0)
    ).astype(int)

    # Stability score: 1 - normalized deviation, clipped
    df["stability_score"] = (1 - v_dev.abs().fillna(1)).clip(-1, 1)

    df["region"] = [
        _stable_region(f"{source_key}-{ts.date() if pd.notna(ts) else 'x'}")
        for ts in df["timestamp"]
    ]
    df["equipment_type"] = "smart_meter"
    df["source_dataset"] = source_key
    return df[COMMON_COLUMNS]


# ----------------------------- entry point ------------------------------ #
def normalize(df: pd.DataFrame, source_key: str) -> pd.DataFrame:
    """Dispatch to the right normalizer based on source_key."""
    if source_key == "stability":
        out = normalize_stability(df)
    elif source_key in ("household", "consumption"):
        out = normalize_household(df, source_key)
    else:
        raise ValueError(f"Unknown source_key: {source_key}")
    logger.info(
        "normalized",
        extra={"source": source_key, "rows": len(out)},
    )
    return out
