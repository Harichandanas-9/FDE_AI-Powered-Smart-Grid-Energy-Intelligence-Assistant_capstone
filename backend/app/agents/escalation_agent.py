"""
Escalation Agent — A2A conditional escalation workflow.

Fired by the orchestrator ONLY when the StabilityAgent reports a
grid_health_score below the critical threshold (30/100).

This is the "Agent-to-Agent escalation workflow" required by the capstone spec:
the Stability Agent's output triggers a conditional branch that routes control
to this agent before RecommendationAgent runs, simulating a real-world
escalation protocol where critical conditions page a senior engineer.

Reads:  envelope["stability_analysis"]["grid_health_score"]
        envelope["stability_analysis"]["region_breakdown"]
        envelope["stability_analysis"]["outage_count"]
Writes: envelope["escalation_required"] = True
        envelope["escalation_reason"]   = str
        envelope["escalation_regions"]  = [str, ...]
        envelope["escalation_health_score"] = float
        Prepends a critical escalation recommendation to envelope["recommendations"]
"""
from __future__ import annotations

from typing import Any, Dict, List

from app.agents.base_agent import BaseAgent

CRITICAL_THRESHOLD = 30.0   # health score below this = critical escalation
WARNING_THRESHOLD  = 50.0   # health score below this = warning escalation


class EscalationAgent(BaseAgent):
    """Raises a WARNING or CRITICAL alert and prepends an escalation recommendation to the envelope."""

    name = "escalation_agent"

    def _run(self, env: Dict[str, Any]) -> tuple[Dict[str, Any], str]:
        """Evaluate the health score and write escalation metadata to the envelope.

        Determines the escalation level (WARNING vs CRITICAL), builds a human-readable
        message, identifies the three most affected regions by incident count, and inserts
        the escalation record at the front of the recommendations list.
        """
        stab   = env.get("stability_analysis") or {}
        health = stab.get("grid_health_score")

        # Should not fire unless orchestrator triggers it, but guard anyway
        if health is None or health >= WARNING_THRESHOLD:
            env["escalation_required"] = False
            return env, "no escalation required"

        outage_count     = int(stab.get("outage_count") or 0)
        region_breakdown = stab.get("region_breakdown") or {}
        anomaly_count    = int(stab.get("anomalies_count") or 0)

        # Identify worst-hit regions by incident count
        worst: List[str] = [
            r for r, _ in sorted(region_breakdown.items(), key=lambda x: -x[1])[:3]
        ]

        level = "CRITICAL" if health < CRITICAL_THRESHOLD else "WARNING"
        level_emoji = "🚨" if health < CRITICAL_THRESHOLD else "⚠️"

        message = (
            f"{level_emoji} {level} ESCALATION — Grid Health Score: {health:.1f}/100 "
            f"(threshold: {CRITICAL_THRESHOLD if health < CRITICAL_THRESHOLD else WARNING_THRESHOLD}). "
            f"Anomalies detected: {anomaly_count}. "
            f"Active outages: {outage_count}. "
            f"Most affected regions: {', '.join(worst) or 'Unknown'}. "
            "Immediate senior grid engineer review required. "
            "Activate emergency response protocol and begin escalation chain."
        )

        env["escalation_required"]      = True
        env["escalation_level"]         = level.lower()
        env["escalation_reason"]        = message
        env["escalation_regions"]       = worst
        env["escalation_health_score"]  = health

        # Prepend critical escalation as the top recommendation
        escalation_rec = {
            "priority":   "critical",
            "action":     message,
            "rationale":  f"A2A escalation triggered: health score {health:.1f}/100 below {CRITICAL_THRESHOLD if health < CRITICAL_THRESHOLD else WARNING_THRESHOLD} threshold",
            "category":   "escalation",
            "escalation": True,
        }
        existing = env.get("recommendations") or []
        env["recommendations"] = [escalation_rec] + existing

        summary = (
            f"{level}: health={health:.1f} outages={outage_count} "
            f"anomalies={anomaly_count} regions={worst}"
        )
        return env, summary
