"""
Grid Stability Agent — deterministic numerical analysis over retrieved
incidents. No LLM. Produces a Grid Health Score (0..100) plus flagged
anomalies for the dashboard gauge + heatmap.

Reads:  envelope["retrieved"]
Writes: envelope["stability_analysis"] = { ... }
"""
from __future__ import annotations

import statistics
from typing import Any, Dict, List

from app.agents.base_agent import BaseAgent

NOMINAL_VOLTAGE = 230.0
NOMINAL_FREQ = 50.0


def _safe(meta: Dict, key: str, default: float = 0.0) -> float:
    try:
        return float(meta.get(key, default))
    except (TypeError, ValueError):
        return default


class StabilityAgent(BaseAgent):
    name = "stability_agent"

    def _run(self, env: Dict[str, Any]) -> tuple[Dict[str, Any], str]:
        chunks: List[Dict] = env.get("retrieved", [])
        if not chunks:
            env["stability_analysis"] = {
                "grid_health_score": None,
                "avg_stability": None,
                "max_voltage_deviation_pct": None,
                "max_frequency_deviation_hz": None,
                "anomalies_count": 0,
                "outage_count": 0,
                "severity_breakdown": {},
                "region_breakdown": {},
            }
            return env, "no incidents — stability analysis skipped"

        voltages = [_safe(c["metadata"], "voltage_mean", NOMINAL_VOLTAGE) for c in chunks]
        freqs = [_safe(c["metadata"], "frequency_mean", NOMINAL_FREQ) for c in chunks]
        stabs = [_safe(c["metadata"], "stability_score_mean") for c in chunks]
        outages = sum(int(c["metadata"].get("outage_event", 0)) for c in chunks)

        v_devs_pct = [abs(v - NOMINAL_VOLTAGE) / NOMINAL_VOLTAGE for v in voltages]
        f_devs = [abs(f - NOMINAL_FREQ) for f in freqs]
        max_v_dev = max(v_devs_pct) if v_devs_pct else 0.0
        max_f_dev = max(f_devs) if f_devs else 0.0

        # Grid Health Score: 100 = perfectly stable, 0 = catastrophic
        # blend of stability_score (avg), v/f deviation, outage count
        avg_stab = statistics.mean(stabs) if stabs else 0.0
        stab_term = max(0.0, min(1.0, (avg_stab + 1) / 2))   # map [-1,1] -> [0,1]
        v_term = max(0.0, 1 - max_v_dev / 0.2)               # full penalty at 20% dev
        f_term = max(0.0, 1 - max_f_dev / 2.0)               # full penalty at 2 Hz dev
        outage_penalty = min(0.3, 0.05 * outages)
        health = round(
            max(0.0, min(100.0, 100 * (0.4 * stab_term + 0.3 * v_term + 0.3 * f_term)
                                 - outage_penalty * 100)),
            1,
        )

        anomalies = sum(1 for v, f in zip(v_devs_pct, f_devs) if v > 0.05 or f > 0.3)

        severity_breakdown: Dict[str, int] = {}
        region_breakdown: Dict[str, int] = {}
        for c in chunks:
            sev = c["metadata"].get("severity", "unknown")
            reg = c["metadata"].get("region", "Unknown")
            severity_breakdown[sev] = severity_breakdown.get(sev, 0) + 1
            region_breakdown[reg] = region_breakdown.get(reg, 0) + 1

        env["stability_analysis"] = {
            "grid_health_score": health,
            "avg_stability": round(avg_stab, 3),
            "max_voltage_deviation_pct": round(max_v_dev * 100, 2),
            "max_frequency_deviation_hz": round(max_f_dev, 3),
            "anomalies_count": anomalies,
            "outage_count": int(outages),
            "severity_breakdown": severity_breakdown,
            "region_breakdown": region_breakdown,
        }
        return env, (f"health={health} anomalies={anomalies} outages={outages}")
