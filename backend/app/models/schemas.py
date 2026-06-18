"""
Shared Pydantic schemas for all API request and response payloads.

Covers health checks, ingestion, guardrail validation, embedding,
retrieval, analysis, chat, feedback, and authentication endpoints.
"""
from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    """Response payload for the /health endpoint."""

    status: str = Field(description="overall status: ok | degraded")
    version: str
    components: Dict[str, str]


# ----- STEP 3 — Ingestion schemas ----------------------------------------- #

class IngestRequest(BaseModel):
    """Request body for triggering CSV ingestion."""

    sources: Optional[List[str]] = Field(
        default=None,
        description="Optional list of source keys: 'stability', 'household', 'consumption'.",
    )
    max_rows: Optional[Dict[str, int]] = Field(
        default=None,
        description="Optional per-source row cap, e.g. {'household': 50000}.",
    )


class IngestResponse(BaseModel):
    """Response payload after an ingestion run, summarizing outcomes per source."""

    status: str
    duration_seconds: float
    chunks_written: int
    per_source: Dict[str, int]
    output_path: str
    errors: List[str]


# ----- Guardrails schemas ------------------------------------------------ #

class ValidateQueryRequest(BaseModel):
    """Request body for the /guardrails/validate endpoint."""

    query: str = Field(description="Raw user-typed query to validate.")


class ValidateQueryResponse(BaseModel):
    """Guardrail verdict returned to the caller with PII and topic-check details."""

    allow: bool = Field(description="True if the query is safe to pass downstream.")
    original_query: str
    masked_query: str = Field(description="Query with PII placeholders inserted.")
    pii_blocked: Dict[str, List[str]] = Field(
        default_factory=dict,
        description="Categories of PII that caused the request to be refused.",
    )
    pii_masked: Dict[str, List[str]] = Field(
        default_factory=dict,
        description="Categories of PII that were masked (request still allowed).",
    )
    off_topic: bool = False
    reasons: List[str] = Field(default_factory=list)
    response_message: str = Field(
        description="Human-friendly message; show as-is to the user when allow=False.",
    )


# ----- STEP 4 — Embedding schemas ---------------------------------------- #

class EmbedRequest(BaseModel):
    """Request body for triggering chunk embedding and ChromaDB upsert."""

    chunks_path: Optional[str] = Field(
        default=None,
        description="Path to chunks.jsonl. Defaults to ./data_processed/chunks.jsonl.",
    )
    limit: Optional[int] = Field(
        default=None, description="Embed only the first N chunks (smoke tests)."
    )
    batch_size: Optional[int] = Field(
        default=256, description="Upsert batch size (chunks per Chroma write)."
    )
    reset: bool = Field(
        default=False,
        description="Drop and recreate the collection before embedding.",
    )


class EmbedResponse(BaseModel):
    """Response payload after embedding chunks into ChromaDB."""

    status: str
    duration_seconds: float
    chunks_embedded: int
    collection_total: int
    embedding_model: str
    persist_dir: str


# ----- STEP 5/6 — Retrieval + analyze schemas ---------------------------- #

class RetrievedChunkOut(BaseModel):
    """A single retrieved document chunk as returned in API responses."""

    id: str
    text: str
    metadata: Dict
    score: float
    semantic_rank: Optional[int] = None
    keyword_rank: Optional[int] = None


class RootCauseOut(BaseModel):
    """A probable root cause identified by the LLM, with supporting evidence IDs."""

    cause: str
    probability: float
    evidence: List[str] = Field(default_factory=list)


class RecommendationOut(BaseModel):
    """An operational recommendation produced by the LLM or template provider."""

    action: str
    priority: str
    rationale: str = ""          # optional — not all providers supply it
    category: Optional[str] = None
    escalation: Optional[bool] = None


class AnalyzeRequest(BaseModel):
    """Request body for the /analyze endpoint."""

    query: str = Field(description="Natural-language operator question.")
    region: Optional[str] = Field(default=None, description="Filter: region name.")
    severity: Optional[str] = Field(default=None, description="Filter: severity tag.")
    source: Optional[str] = Field(default=None, description="Filter: source_dataset.")
    top_k: Optional[int] = Field(default=None, description="Override final_top_k.")


class AgentTraceItem(BaseModel):
    """Execution trace for a single agent step, used in multi-agent responses."""

    agent: str
    status: str
    duration_ms: float = 0.0
    summary: str = ""
    error: Optional[str] = None


class AnalyzeResponse(BaseModel):
    """Full response payload from the /analyze endpoint."""

    status: str = Field(description="'ok' or 'refused'")
    guardrail: Dict
    query: Optional[str] = None
    masked_query: Optional[str] = None
    answer: str = ""
    root_causes: List[RootCauseOut] = Field(default_factory=list)
    recommendations: List[RecommendationOut] = Field(default_factory=list)
    confidence: float = 0.0
    reasoning: str = ""
    retrieved: List[RetrievedChunkOut] = Field(default_factory=list)
    stability_analysis: Optional[Dict] = None
    agent_trace: List[AgentTraceItem] = Field(default_factory=list)
    provider: str = "template"
    duration_seconds: float = 0.0
    operator: Optional[str] = None
    tenant_id: Optional[str] = None
    escalation_required: Optional[bool] = None
    escalation_level: Optional[str] = None
    escalation_reason: Optional[str] = None
    escalation_regions: Optional[List[str]] = None



# ----- Chat / feedback schemas ------------------------------------------- #

class ChatRequest(BaseModel):
    """Request body for the /chat endpoint."""

    query: str
    session_id: Optional[str] = None


class ChatResponse(BaseModel):
    """Response payload from the /chat endpoint, including agent outputs and cache status."""

    answer: str
    session_id: str
    intent: Optional[str] = None
    severity: Optional[str] = None
    retrieved_docs: List[RetrievedChunkOut] = Field(default_factory=list)
    agent_outputs: Dict = Field(default_factory=dict)
    reformulated_from: Optional[str] = None
    from_cache: bool = False


class FeedbackRequest(BaseModel):
    """Request body for submitting a thumbs-up/down rating on an answer."""

    session_id: str
    message_id: str
    rating: int
    comment: Optional[str] = None


# ----- Auth schemas ------------------------------------------------------- #

class LoginResponse(BaseModel):
    """JWT token payload returned after a successful login."""

    access_token: str
    token_type: str
    expires_at: str
    tenant_id: str
    username: str
    role: str


class MeResponse(BaseModel):
    """Authenticated user identity returned by the /me endpoint."""

    username: str
    tenant_id: str
    role: str
