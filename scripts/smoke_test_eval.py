"""Smoke test for STEP 14 — evaluation pipeline (heuristic fallback)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(BACKEND_DIR))

from app.evaluation import deepeval_runner, llm_judge, metrics as heur  # noqa: E402


SAMPLE = {
    "status": "ok",
    "query": "Voltage instability in South Zone during peak demand",
    "answer": (
        "Voltage in South Zone dropped to 218V during the evening peak with "
        "transformer overload risk. Stability index averaged -0.4 (unstable). "
        "Likely caused by demand exceeding feeder capacity."
    ),
    "root_causes": [
        {"cause": "Transformer overload risk", "probability": 0.78,
         "evidence": ["st-South-2024011518"]},
        {"cause": "Voltage deviation from nominal", "probability": 0.65,
         "evidence": ["st-South-2024011518", "st-South-2024011519"]},
    ],
    "recommendations": [
        {"action": "Schedule load redistribution from South Zone during peak windows.",
         "priority": "high",
         "rationale": "Repeated overload-risk classifications in retrieved incidents."},
        {"action": "Inspect tap changers and voltage regulators on affected feeders.",
         "priority": "medium",
         "rationale": "Voltage deviation exceeds 5% threshold."},
    ],
    "confidence": 0.78,
    "reasoning": "Retrieved 4 similar incidents, all critical/high severity in South Zone.",
    "retrieved": [
        {"id": "st-South-2024011518", "score": 0.93,
         "text": "South Zone voltage 218V transformer overload 49.45Hz outage demand 9.8kW critical"},
        {"id": "st-South-2024011519", "score": 0.88,
         "text": "South Zone voltage 220V transformer overload 49.6Hz demand 9.2kW high severity"},
    ],
}

def main() -> int:
    print("=== HEURISTIC METRICS ===")
    h = heur.evaluate(SAMPLE)
    for k, v in h.items():
        print(f"  {k:<24} {v}")

    print("\n=== DEEPEVAL (no API key — heuristic provider) ===")
    d = deepeval_runner.run(SAMPLE["query"], SAMPLE)
    for k, v in d.items():
        print(f"  {k:<24} {v}")
    assert d["provider"] == "heuristic"
    assert d["faithfulness"] >= 0

    print("\n=== LLM JUDGE (no API key — heuristic fallback) ===")
    j = llm_judge.judge(SAMPLE["query"], SAMPLE)
    for k, v in j.items():
        print(f"  {k:<24} {v}")

    print("\n[smoke] OK ✓")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
