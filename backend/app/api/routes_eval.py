"""
POST /api/v1/evaluate — evaluate one /analyze response.

Body: { query: str, response: AnalyzeResponse-like dict }
Returns: { deepeval: {...}, llm_judge: {...}, heuristic: {...}, summary }
"""
from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Body, Depends

from app.core.security import get_current_principal
from app.evaluation import deepeval_runner, llm_judge, metrics as heur

router = APIRouter(tags=["evaluation"])


def _summary(d: Dict[str, Any], j: Dict[str, Any]) -> Dict[str, float]:
    """Aggregate score in [0,1] for the UI badge."""
    parts = [
        d.get("faithfulness", 0),
        d.get("answer_relevancy", 0),
        d.get("format_correctness", 0),
        j.get("accuracy", 0),
        j.get("actionability", 0),
    ]
    valid = [p for p in parts if isinstance(p, (int, float))]
    overall = round(sum(valid) / max(1, len(valid)), 3) if valid else 0.0
    return {"overall": overall, "n_metrics": len(valid)}


@router.post("/evaluate", summary="Evaluate an /analyze response")
async def evaluate(
    body: Dict[str, Any] = Body(...),
    principal: dict = Depends(get_current_principal),
) -> Dict[str, Any]:
    query = body.get("query") or body.get("response", {}).get("query") or ""
    response = body.get("response") or body

    deep = deepeval_runner.run(query, response)
    judge = llm_judge.judge(query, response)
    h = heur.evaluate(response)

    return {
        "tenant_id": principal["tenant_id"],
        "deepeval":  deep,
        "llm_judge": judge,
        "heuristic": h,
        "summary":   _summary(deep, judge),
    }
