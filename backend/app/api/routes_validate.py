"""
POST /api/v1/validate-query — run guardrails on a user query.

Use this to test the guardrail behavior without running the full /analyze chain
(which doesn't exist until STEP 6). When /analyze is built, it will call
validate_query() internally and short-circuit if the verdict denies the query.
"""
from __future__ import annotations

from fastapi import APIRouter

from app.models.schemas import ValidateQueryRequest, ValidateQueryResponse
from app.utils.guardrails import validate_query

router = APIRouter(prefix="/guardrails", tags=["guardrails"])


@router.post(
    "/validate-query",
    response_model=ValidateQueryResponse,
    summary="Run input guardrails (PII + topic) on a query",
)
async def validate(req: ValidateQueryRequest) -> ValidateQueryResponse:
    verdict = validate_query(req.query)
    return ValidateQueryResponse(**verdict.to_dict())
