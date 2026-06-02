"""
Prompt templates for the smart-grid RAG pipeline.

We keep prompts as plain strings (not LangChain prompt templates) for two
reasons: easier to print and debug, and easier to ensure the JSON-output
contract is stable. The contract is enforced by pydantic on the response.
"""
from __future__ import annotations

from typing import List

from app.rag.hybrid_retriever import RetrievedChunk

# ---------------------------------------------------------------------------
SYSTEM_PROMPT = """You are an AI grid-operations assistant for a power utility.

You answer questions from utility engineers about power-grid incidents using
ONLY the historical incident records provided in the CONTEXT block. You do
not invent details. If the context does not contain enough information to
answer, say so.

Always respond in valid JSON matching this schema exactly:
{
  "answer": "<one-paragraph explanation in plain English, 3–5 sentences>",
  "root_causes": [
     {"cause": "<short phrase>", "probability": <0..1>, "evidence": ["<incident_id>"]}
  ],
  "recommendations": [
     {"action": "<concrete operational action>", "priority": "low|medium|high|critical",
      "rationale": "<one sentence tying the action to the evidence>"}
  ],
  "confidence": <0..1>,
  "reasoning": "<2–3 sentences explaining how the retrieved incidents lead to this answer>"
}

Rules:
- Stay grounded in CONTEXT. Cite incident_ids in `evidence`.
- Use power-system vocabulary precisely (voltage, frequency, transformer, demand).
- Output JSON ONLY — no preamble, no markdown fences, no trailing text.
"""

USER_PROMPT_TEMPLATE = """CONTEXT (top relevant historical incidents):
{context_block}

USER QUERY: {query}

Respond with the JSON object as instructed."""


def build_context_block(chunks: List[RetrievedChunk], char_cap: int = 350) -> str:
    """Build the CONTEXT block — one chunk per line with id + truncated text."""
    lines = []
    for c in chunks:
        snippet = c.text[:char_cap]
        meta = c.metadata
        lines.append(
            f"[{c.id}] (region={meta.get('region','?')}, "
            f"severity={meta.get('severity','?')}, "
            f"source={meta.get('source_dataset','?')}) {snippet}"
        )
    return "\n".join(lines) if lines else "(no incidents retrieved)"


def build_user_prompt(query: str, chunks: List[RetrievedChunk]) -> str:
    return USER_PROMPT_TEMPLATE.format(
        context_block=build_context_block(chunks),
        query=query,
    )
