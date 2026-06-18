"""
Templater — converts each aggregated incident row into a NATURAL-LANGUAGE
NARRATIVE that the vector store will later embed.

Why prose over JSON
-------------------
Sentence-transformer embeddings are trained on natural language. Embedding a
JSON blob gives weak similarity. A sentence like:

    "On 2024-03-12 18:00 in South Zone, smart_meter readings showed a voltage
    of 218.4 V (high deviation), current at 12.3 A and demand peaking at
    9.8 kW. Frequency averaged 49.6 Hz. Stability index 0.21 (moderate).
    Transformer status: warning. Outage events: 0. Severity: high."

embeds well, retrieves on conceptual queries ("voltage dip evening peak"), AND
remains readable when surfaced as evidence in the dashboard.
"""
from __future__ import annotations

from typing import Any

import pandas as pd


def _fmt(x: Any, digits: int = 2) -> str:
    """Format a value as a fixed-decimal string, falling back to str() on non-numerics."""
    try:
        return f"{float(x):.{digits}f}"
    except (TypeError, ValueError):
        return str(x)


def render_incident(row: pd.Series) -> str:
    """Return a natural-language paragraph for a single aggregated incident."""
    ts = row["window_start"]
    ts_str = ts.strftime("%Y-%m-%d %H:%M") if pd.notna(ts) else "unknown time"

    v_dev = abs(row["voltage_mean"] - 230.0) / 230.0
    v_dev_label = ("nominal" if v_dev < 0.03
                   else "moderate deviation" if v_dev < 0.08
                   else "high deviation")

    f_dev = abs(row["frequency_mean"] - 50.0)
    f_dev_label = ("nominal" if f_dev < 0.3
                   else "moderate drift" if f_dev < 0.8
                   else "significant drift")

    stab = row["stability_score_mean"]
    stab_label = ("stable" if stab > 0.5
                  else "moderate" if stab > 0
                  else "unstable")

    outage_str = (
        "no outage events recorded"
        if row["outage_count"] == 0
        else f"{int(row['outage_count'])} outage event(s) detected"
    )

    return (
        f"On {ts_str} in {row['region']}, {row['equipment_type']} readings "
        f"showed a voltage of {_fmt(row['voltage_mean'])} V ({v_dev_label}), "
        f"current at {_fmt(row.get('current_mean', 0))} A and demand "
        f"peaking at {_fmt(row['demand_max'])} kW. Frequency averaged "
        f"{_fmt(row['frequency_mean'])} Hz ({f_dev_label}). Stability index "
        f"{_fmt(stab)} ({stab_label}). Transformer status: "
        f"{row['transformer_status']}. {outage_str.capitalize()}. "
        f"Severity classified as {row['severity']}. "
        f"Source dataset: {row['source_dataset']}."
    )


def render_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """Add a 'text' column with the narrative for every row."""
    df = df.copy()
    df["text"] = df.apply(render_incident, axis=1)
    return df


def chunk_to_dict(row: pd.Series, tenant_id: str = "default") -> dict:
    """Serialize one aggregated row to the canonical chunk format.

    `tenant_id` is included so the same Chroma collection can serve multiple
    tenants. Defaults to 'default' for single-tenant operation.
    """
    return {
        "id": row["incident_id"],
        "text": row["text"],
        "metadata": {
            "tenant_id": tenant_id,
            "region": row["region"],
            "equipment_type": row["equipment_type"],
            "severity": row["severity"],
            "transformer_status": row["transformer_status"],
            "outage_event": int(row["outage_event"]),
            "source_dataset": row["source_dataset"],
            "window_start": row["window_start"].isoformat()
                if pd.notna(row["window_start"]) else None,
            "window_end": row["window_end"].isoformat()
                if pd.notna(row["window_end"]) else None,
            "voltage_mean": float(row["voltage_mean"]),
            "frequency_mean": float(row["frequency_mean"]),
            "demand_max": float(row["demand_max"]),
            "stability_score_mean": float(row["stability_score_mean"]),
            "row_count": int(row["row_count"]),
        },
    }
