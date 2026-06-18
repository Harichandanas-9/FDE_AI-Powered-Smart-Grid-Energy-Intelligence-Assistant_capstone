"""
GET /api/v1/predict — Predictive Grid Failure Intelligence.

Analyses current ChromaDB data to predict:
- Transformer overload risk in the next operational window
- Grid stability risk score
- Proactive alerts per region
- Recommended pre-emptive actions

This is a deterministic rule-based predictor that uses the same telemetry
data stored in ChromaDB — no LLM required for the prediction itself.
The predictions are grounded in real historical patterns.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Any, Dict, List

from fastapi import APIRouter, Depends

from app.core.config import get_settings
from app.core.security import get_current_principal
from app.services.analytics_service import _fetch_all

router = APIRouter(tags=["predict"])

NOMINAL_VOLTAGE = 230.0
NOMINAL_FREQ = 50.0
OVERLOAD_VOLTAGE_THRESHOLD = 0.08   # 8% deviation = high risk
OVERLOAD_VOLTAGE_WARNING   = 0.05   # 5% deviation = medium risk
FREQ_CRITICAL = 0.8
FREQ_WARNING  = 0.4


def _risk_level(score: float) -> str:
    """Map a composite risk score in [0, 1] to a human-readable risk level string."""
    if score >= 0.75: return "critical"
    if score >= 0.55: return "high"
    if score >= 0.35: return "medium"
    return "low"


def _predict_region(chunks: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Compute a composite failure-risk prediction for a set of telemetry chunks.

    Aggregates voltage deviation, frequency deviation, stability index, outage events,
    and transformer overload rate into a weighted composite score, then generates
    human-readable alerts and prioritised recommendations.
    """
    if not chunks:
        return {"risk_score": 0.0, "risk_level": "low", "alerts": [], "recommendations": []}
    
    voltages  = [float(c["metadata"].get("voltage_mean", NOMINAL_VOLTAGE) or NOMINAL_VOLTAGE) for c in chunks]
    freqs     = [float(c["metadata"].get("frequency_mean", NOMINAL_FREQ) or NOMINAL_FREQ) for c in chunks]
    stabs     = [float(c["metadata"].get("stability_score_mean", 0) or 0) for c in chunks]
    demands   = [float(c["metadata"].get("demand_max", 0) or 0) for c in chunks]
    outages   = sum(int(c["metadata"].get("outage_event", 0)) for c in chunks)
    overloads = sum(1 for c in chunks if c["metadata"].get("transformer_status") == "overload_risk")
    
    n = len(chunks)
    avg_v  = sum(voltages) / n
    avg_f  = sum(freqs) / n
    avg_s  = sum(stabs) / n
    max_d  = max(demands) if demands else 0
    
    v_dev = abs(avg_v - NOMINAL_VOLTAGE) / NOMINAL_VOLTAGE
    f_dev = abs(avg_f - NOMINAL_FREQ)
    
    # Risk components
    voltage_risk  = min(1.0, v_dev / 0.10)
    freq_risk     = min(1.0, f_dev / 1.0)
    stab_risk     = max(0.0, (-avg_s + 1) / 2)
    outage_risk   = min(1.0, outages / max(n, 1))
    overload_risk = min(1.0, overloads / max(n, 1))
    
    composite = (
        0.30 * voltage_risk +
        0.20 * freq_risk +
        0.25 * stab_risk +
        0.15 * outage_risk +
        0.10 * overload_risk
    )
    risk_lvl = _risk_level(composite)
    
    alerts = []
    recs   = []
    
    if v_dev >= OVERLOAD_VOLTAGE_THRESHOLD:
        alerts.append(f"⚡ Critical voltage deviation ({v_dev*100:.1f}% from nominal {NOMINAL_VOLTAGE}V)")
        recs.append({"priority": "critical", "action": "Deploy voltage regulators immediately and check for short circuits", "category": "voltage"})
    elif v_dev >= OVERLOAD_VOLTAGE_WARNING:
        alerts.append(f"⚠ Elevated voltage deviation ({v_dev*100:.1f}%)")
        recs.append({"priority": "high", "action": "Monitor voltage regulators and inspect transformer tap settings", "category": "voltage"})
    
    if f_dev >= FREQ_CRITICAL:
        alerts.append(f"🔄 Frequency deviation critical ({avg_f:.2f} Hz vs 50 Hz nominal)")
        recs.append({"priority": "critical", "action": "Activate frequency regulation — check generator governors and load shedding protocols", "category": "frequency"})
    elif f_dev >= FREQ_WARNING:
        alerts.append(f"⚠ Frequency drift detected ({avg_f:.2f} Hz)")
        recs.append({"priority": "high", "action": "Review generator output balance and interconnection load", "category": "frequency"})
    
    if overload_risk >= 0.5:
        alerts.append(f"🔥 Transformer overload risk in {overloads}/{n} windows ({overload_risk*100:.0f}%)")
        recs.append({"priority": "critical", "action": "Reduce transformer load immediately via load transfer to adjacent feeders", "category": "transformer"})
    
    if avg_s < -0.3:
        alerts.append(f"📉 Grid stability index negative (avg {avg_s:.3f})")
        recs.append({"priority": "high", "action": "Initiate stability monitoring protocol — review reactive power compensation", "category": "stability"})
    
    if outages > 0:
        alerts.append(f"🚨 {outages} outage event(s) detected in recent history")
        recs.append({"priority": "high", "action": "Review outage root causes and ensure restoration plans are activated", "category": "outage"})
    
    if max_d > 0 and v_dev > 0.03:
        trend = "rising" if demands[-1] > demands[0] else "stable"
        alerts.append(f"📊 Peak demand {max_d:.1f} kW with voltage stress ({trend} trend)")
        recs.append({"priority": "medium", "action": "Implement demand response programme to flatten peak load", "category": "demand"})
    
    if not alerts:
        alerts.append("✅ No immediate failure indicators detected in this region")
    
    return {
        "risk_score":         round(composite, 3),
        "risk_level":         risk_lvl,
        "voltage_deviation_pct": round(v_dev * 100, 2),
        "frequency_deviation_hz": round(f_dev, 3),
        "avg_stability_index": round(avg_s, 3),
        "transformer_overload_pct": round(overload_risk * 100, 1),
        "outage_events":      outages,
        "n_windows_analysed": n,
        "alerts":             alerts,
        "recommendations":    recs,
    }


@router.get("/predict", summary="Predictive Grid Failure Intelligence")
async def predict_failures(
    principal: dict = Depends(get_current_principal),
) -> Dict[str, Any]:
    """
    Analyses stored telemetry to predict transformer overload risk,
    grid instability, and proactive mitigation needs per region.
    Returns overall + per-region prediction with prioritized alerts.
    """
    tenant_id = principal["tenant_id"]
    rows = _fetch_all(tenant_id, max_rows=5000)
    
    if not rows:
        return {
            "tenant_id": tenant_id,
            "status": "no_data",
            "message": "No telemetry data found. Run ETL first.",
            "overall": {"risk_score": 0, "risk_level": "low", "alerts": [], "recommendations": []},
            "per_region": {},
            "global_alerts": [],
            "n_incidents_analysed": 0,
        }
    
    # Group by region
    by_region: Dict[str, List] = defaultdict(list)
    for r in rows:
        reg = r["metadata"].get("region", "Unknown")
        by_region[reg].append(r)
    
    # Per-region predictions
    per_region: Dict[str, Any] = {}
    for reg, chunks in by_region.items():
        per_region[reg] = _predict_region(chunks)
    
    # Global prediction (all data)
    overall = _predict_region(rows)
    
    # Global alerts = regions with critical or high risk
    global_alerts: List[str] = []
    for reg, pred in sorted(per_region.items(), key=lambda x: -x[1]["risk_score"]):
        if pred["risk_level"] in ("critical", "high"):
            global_alerts.append(
                f"Region '{reg}': {pred['risk_level'].upper()} risk ({pred['risk_score']:.2f}) — "
                + (pred["alerts"][0] if pred["alerts"] else "")
            )
    
    if not global_alerts:
        global_alerts.append("✅ Grid operating within normal parameters across all monitored regions")
    
    return {
        "tenant_id":           tenant_id,
        "status":              "ok",
        "overall":             overall,
        "per_region":          per_region,
        "global_alerts":       global_alerts,
        "highest_risk_region": max(per_region, key=lambda r: per_region[r]["risk_score"]) if per_region else None,
        "n_incidents_analysed": len(rows),
        "n_regions":           len(per_region),
    }
