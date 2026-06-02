"""
Recommendation Agent — final synthesis stage.

Takes the full envelope (retrieved + stability + root_causes) and asks the
LLM to produce a natural-language answer, recommendations, reasoning, and
confidence. Falls back to TemplateProvider when no LLM is configured.

This agent is the ONLY one that calls an LLM. All upstream agents are
deterministic, which gives the panel a clean story: "the AI explains,
the algorithms decide."

Reads:  entire envelope
Writes: envelope["answer"], ["recommendations"], ["reasoning"], ["confidence"]
"""
from __future__ import annotations

import json
from typing import Any, Dict, List

from app.agents.base_agent import BaseAgent
from app.rag.hybrid_retriever import RetrievedChunk
from app.rag.llm import TemplateProvider


def _to_chunks(chunk_dicts: List[Dict]) -> List[RetrievedChunk]:
    return [
        RetrievedChunk(
            id=c["id"], text=c["text"], metadata=c.get("metadata", {}),
            score=c.get("score", 0.0),
            semantic_rank=c.get("semantic_rank"),
            keyword_rank=c.get("keyword_rank"),
        )
        for c in chunk_dicts
    ]


class RecommendationAgent(BaseAgent):
    name = "recommendation_agent"

    def __init__(self, settings, llm_provider):
        super().__init__(settings)
        self.llm = llm_provider

    def _run(self, env: Dict[str, Any]) -> tuple[Dict[str, Any], str]:
        query = env.get("masked_query") or env.get("query", "")
        chunks_dicts = env.get("retrieved", [])
        chunks = _to_chunks(chunks_dicts)

        # Build an enriched query context — pass the structured causes +
        # stability analysis to the LLM as JSON so it can ground its prose.
        causes = env.get("root_causes", [])
        stab = env.get("stability_analysis", {})
        if causes or stab:
            enriched = (
                f"{query}\n\n"
                f"Prior analysis (use this — don't invent):\n"
                f"{json.dumps({'stability': stab, 'root_causes': causes}, default=str)}"
            )
        else:
            enriched = query

        try:
            raw = self.llm.generate(enriched, chunks)
        except Exception:
            raw = TemplateProvider().generate(enriched, chunks)
            provider_name = f"{self.llm.name}->template_fallback"
        else:
            provider_name = self.llm.name

        env["answer"] = str(raw.get("answer", ""))
        # Prefer the deterministic causes from FailureAgent over LLM ones.
        if not env.get("root_causes"):
            env["root_causes"] = raw.get("root_causes", [])
        env["recommendations"] = raw.get("recommendations", [])
        env["reasoning"] = str(raw.get("reasoning", ""))
        try:
            env["confidence"] = float(raw.get("confidence", 0.5))
        except (TypeError, ValueError):
            env["confidence"] = 0.5
        env["provider"] = provider_name
        n_recs = len(env["recommendations"])
        return env, f"provider={provider_name} recs={n_recs} conf={env['confidence']}"
