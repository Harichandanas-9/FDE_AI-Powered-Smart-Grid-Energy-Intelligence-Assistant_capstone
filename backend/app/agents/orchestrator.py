"""
Multi-Agent Orchestrator.

Sequential A2A pipeline:
    Guardrails  ->  Retrieval  ->  Stability  ->  Failure  ->  Recommendation

The orchestrator owns the envelope, runs each agent via `execute()` (which
records timing + trace), and never lets a single agent's failure abort the
chain. The trace is exposed in the response for the UI's agent-flow viz.
"""
from __future__ import annotations

import time
from typing import Any, Dict, Optional

from app.agents.base_agent import BaseAgent
from app.agents.failure_agent import FailureAgent
from app.agents.recommendation_agent import RecommendationAgent
from app.agents.retrieval_agent import RetrievalAgent
from app.agents.stability_agent import StabilityAgent
from app.agents.escalation_agent import EscalationAgent
from app.core.config import Settings, get_settings
from app.core.logging import get_logger
from app.rag.bm25_index import BM25Index
from app.rag.hybrid_retriever import HybridRetriever
from app.rag.llm import get_provider
from app.utils.guardrails import GuardrailVerdict, validate_query

logger = get_logger(__name__)


class AgentOrchestrator:
    def __init__(self, settings: Optional[Settings] = None,
                 bm25_index: Optional[BM25Index] = None):
        self.settings = settings or get_settings()
        retriever = HybridRetriever(self.settings, bm25_index=bm25_index)
        llm = get_provider(self.settings)

        self.agents: list[BaseAgent] = [
            RetrievalAgent(self.settings, retriever=retriever),
            StabilityAgent(self.settings),
            FailureAgent(self.settings),
            RecommendationAgent(self.settings, llm_provider=llm),
        ]
        self.escalation_agent = EscalationAgent(self.settings)
        logger.info(
            "orchestrator_ready",
            extra={"agents": [a.name for a in self.agents], "llm": llm.name},
        )

    # ----------------------------------------------------------------------
    def run(self, query: str, *, tenant_id: str = "default",
            filters: Optional[Dict[str, Any]] = None,
            top_k: Optional[int] = None) -> Dict[str, Any]:
        t0 = time.time()

        # ----- Guardrails (synchronous, before any agent fires) -----
        verdict: GuardrailVerdict = validate_query(query)
        envelope: Dict[str, Any] = {
            "query": query,
            "masked_query": verdict.masked_query,
            "tenant_id": tenant_id,
            "filters": filters or {},
            "top_k": top_k,
            "guardrail": verdict.to_dict(),
            "agent_trace": [{
                "agent": "guardrails", "status": "ok" if verdict.allow else "refused",
                "duration_ms": 0, "summary": ",".join(verdict.reasons), "error": None,
            }],
            "retrieved": [],
            "stability_analysis": {},
            "root_causes": [],
            "recommendations": [],
            "answer": verdict.response_message if not verdict.allow else "",
            "reasoning": "",
            "confidence": 0.0,
        }

        if not verdict.allow:
            envelope["status"] = "refused"
            envelope["duration_seconds"] = round(time.time() - t0, 3)
            envelope["provider"] = "guardrails"
            return envelope

        # ----- Sequential A2A pipeline with conditional escalation -----
        for agent in self.agents:
            envelope = agent.execute(envelope)

            # A2A ESCALATION BRANCH: after StabilityAgent, check if grid is
            # in a critical or warning state and conditionally escalate.
            if agent.name == "stability_agent":
                health = (envelope.get("stability_analysis") or {}).get("grid_health_score")
                if health is not None and health < 50.0:
                    # Trigger EscalationAgent before Failure/Recommendation agents run
                    envelope = self.escalation_agent.execute(envelope)
                    logger.info(
                        "a2a_escalation_triggered",
                        extra={
                            "health_score": health,
                            "level": envelope.get("escalation_level", "unknown"),
                            "regions": envelope.get("escalation_regions", []),
                        },
                    )

        envelope["status"] = "ok"
        envelope["duration_seconds"] = round(time.time() - t0, 3)
        return envelope
