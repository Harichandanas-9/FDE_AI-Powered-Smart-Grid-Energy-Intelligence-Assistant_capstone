"""
Failure Analysis Agent — rule-based root-cause identification from the
combination of retrieved incidents + stability analysis.

Deterministic by design: the explainability we surface to the panel must
be reproducible. The LLM (in RecommendationAgent) wraps these rule-derived
causes in natural-language narrative; the structured causes themselves are
not invented by the LLM.

Reads:  envelope["retrieved"], envelope["stability_analysis"]
Writes: envelope["root_causes"] = [ {cause, probability, evidence}, ... ]
"""
from __future__ import annotations

from collections import Counter
from typing import Any, Dict, List

from app.agents.base_agent import BaseAgent


class FailureAgent(BaseAgent):
    """Deterministically identifies probable root causes from retrieved incidents and stability metrics."""

    name = "failure_analysis_agent"

    def _run(self, env: Dict[str, Any]) -> tuple[Dict[str, Any], str]:
        """Apply rule-based heuristics to derive a ranked list of root cause candidates.

        Checks voltage deviation, frequency drift, transformer overload concentration,
        outage clustering, and smart-meter anomaly patterns. Appends a generic fallback
        entry when no specific rule matches.
        """
        chunks: List[Dict] = env.get("retrieved", [])
        stab = env.get("stability_analysis", {}) or {}

        if not chunks:
            env["root_causes"] = []
            return env, "no incidents — no causes derived"

        causes: List[Dict] = []

        # Helper: top-2 chunk ids as evidence
        ev_top = [c["id"] for c in chunks[:2]]

        # 1) Voltage deviation
        v_dev = float(stab.get("max_voltage_deviation_pct") or 0)
        if v_dev > 8:
            causes.append({
                "cause": f"Severe voltage deviation ({v_dev:.1f}% from nominal)",
                "probability": min(0.95, 0.5 + v_dev / 20),
                "evidence": ev_top,
            })
        elif v_dev > 3:
            causes.append({
                "cause": f"Moderate voltage deviation ({v_dev:.1f}%)",
                "probability": 0.55,
                "evidence": ev_top,
            })

        # 2) Frequency drift
        f_dev = float(stab.get("max_frequency_deviation_hz") or 0)
        if f_dev > 0.8:
            causes.append({
                "cause": f"Grid frequency drift ({f_dev:.2f} Hz off 50 Hz)",
                "probability": min(0.9, 0.5 + f_dev / 2),
                "evidence": ev_top,
            })

        # 3) Transformer status concentration
        statuses = Counter(c["metadata"].get("transformer_status") for c in chunks)
        if statuses.get("overload_risk", 0) >= len(chunks) / 2:
            causes.append({
                "cause": "Recurring transformer overload risk across retrieved incidents",
                "probability": 0.78,
                "evidence": [c["id"] for c in chunks
                             if c["metadata"].get("transformer_status") == "overload_risk"][:3],
            })

        # 4) Outage cluster
        outage_count = int(stab.get("outage_count") or 0)
        if outage_count >= 1:
            causes.append({
                "cause": f"Outage events present in {outage_count} retrieved window(s)",
                "probability": min(0.85, 0.5 + 0.1 * outage_count),
                "evidence": [c["id"] for c in chunks
                             if c["metadata"].get("outage_event")][:3],
            })

        # 5) Smart-meter anomaly cluster
        sources = Counter(c["metadata"].get("source_dataset") for c in chunks)
        if sources.get("household", 0) >= 2:
            causes.append({
                "cause": "Clustered smart-meter anomalies suggesting localized "
                         "consumption irregularity",
                "probability": 0.6,
                "evidence": [c["id"] for c in chunks
                             if c["metadata"].get("source_dataset") == "household"][:3],
            })

        # 6) Fallback if nothing strong fired
        if not causes:
            causes.append({
                "cause": "Operational anomaly under similar past conditions "
                         "(no dominant single-cause signature)",
                "probability": 0.4,
                "evidence": ev_top,
            })

        env["root_causes"] = causes
        return env, f"{len(causes)} candidate root cause(s)"
