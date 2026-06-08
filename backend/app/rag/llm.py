"""
LLM provider abstraction with an offline-safe fallback.

Why a fallback?
---------------
The capstone demo cannot be one missing API key away from failure. The
"template" provider synthesizes a structured answer purely from the retrieved
chunks using deterministic rules, so /analyze always returns something useful.

Providers
---------
  openai      -> OpenAI Chat Completions (langchain-openai)
  anthropic   -> Anthropic Messages (langchain-anthropic)
  template    -> deterministic, no external API calls
  auto        -> use openai/anthropic if configured, else template
"""
from __future__ import annotations

import json
from collections import Counter
from typing import Any, Dict, List, Optional

from app.core.config import Settings, get_settings
from app.core.logging import get_logger
from app.rag.hybrid_retriever import RetrievedChunk
from app.rag.prompt_templates import SYSTEM_PROMPT, build_user_prompt

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
def _extract_json(text: str) -> Dict[str, Any]:
    """Robust JSON extraction — tolerates ```json fences and trailing prose."""
    t = (text or "").strip()
    if t.startswith("```"):
        # strip markdown fence
        t = t.strip("`")
        if t.lower().startswith("json"):
            t = t[4:].lstrip()
    # find first '{' and last '}'
    start = t.find("{")
    end = t.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("no JSON object in LLM output")
    return json.loads(t[start:end + 1])


# ---------------------------------------------------------------------------
class TemplateProvider:
    """
    Deterministic, offline. Builds a sensible JSON answer from retrieved
    chunks using severity / region / transformer_status frequency.
    """
    name = "template"

    def generate(self, query: str, chunks: List[RetrievedChunk]) -> Dict[str, Any]:
        if not chunks:
            return {
                "answer": (
                    "I couldn't find historical incidents matching this query. "
                    "Try broadening your terms (e.g. region, equipment, or "
                    "stability symptom)."
                ),
                "root_causes": [],
                "recommendations": [],
                "confidence": 0.0,
                "reasoning": "No relevant incidents retrieved from the vector store.",
            }

        sev_counter = Counter(c.metadata.get("severity", "low") for c in chunks)
        status_counter = Counter(
            c.metadata.get("transformer_status", "unknown") for c in chunks
        )
        region_counter = Counter(c.metadata.get("region", "Unknown") for c in chunks)
        top_region = region_counter.most_common(1)[0][0]
        top_sev = sev_counter.most_common(1)[0][0]
        top_status = status_counter.most_common(1)[0][0]

        # Average key telemetry
        avg_v = sum(float(c.metadata.get("voltage_mean", 230)) for c in chunks) / len(chunks)
        avg_f = sum(float(c.metadata.get("frequency_mean", 50)) for c in chunks) / len(chunks)
        max_d = max(float(c.metadata.get("demand_max", 0)) for c in chunks)

        # Root-cause heuristic
        causes = []
        if top_status == "overload_risk":
            causes.append({
                "cause": "Transformer overload risk",
                "probability": 0.75,
                "evidence": [chunks[0].id],
            })
        if abs(avg_v - 230) / 230 > 0.05:
            causes.append({
                "cause": f"Voltage deviation from nominal (avg {avg_v:.1f} V)",
                "probability": 0.65,
                "evidence": [c.id for c in chunks[:2]],
            })
        if abs(avg_f - 50) > 0.5:
            causes.append({
                "cause": f"Grid frequency drift (avg {avg_f:.2f} Hz)",
                "probability": 0.6,
                "evidence": [c.id for c in chunks[:2]],
            })
        if not causes:
            causes.append({
                "cause": "Operational anomaly under similar conditions",
                "probability": 0.4,
                "evidence": [chunks[0].id],
            })

        # Recommendations
        recs = []
        if top_status == "overload_risk":
            recs.append({
                "action": f"Schedule load redistribution from {top_region} during peak demand windows.",
                "priority": "high",
                "rationale": "Repeated overload-risk classifications in retrieved incidents.",
            })
        if abs(avg_v - 230) / 230 > 0.05:
            recs.append({
                "action": "Inspect tap changers and voltage regulators on affected feeders.",
                "priority": "high" if top_sev in ("high", "critical") else "medium",
                "rationale": "Average voltage in retrieved incidents deviates from nominal.",
            })
        if abs(avg_f - 50) > 0.5:
            recs.append({
                "action": "Coordinate with grid-balancing authority for primary-reserve dispatch.",
                "priority": "high",
                "rationale": "Frequency drift detected across similar past events.",
            })
        if not recs:
            recs.append({
                "action": "Continue monitoring; no immediate corrective action indicated.",
                "priority": "low",
                "rationale": "Retrieved incidents do not present clear failure signatures.",
            })

        answer = (
            "Grid Analysis - " + top_region + " Zone\n\n"
            "Based on " + str(len(chunks)) + " similar historical incidents "
            "(predominantly in " + top_region + ", severity: " + top_sev + "), "
            "the system identified a recurring pattern of " + top_status.replace("_"," ") + " conditions.\n\n"
            "Key Telemetry Readings:\n"
            "- Average Voltage: " + str(round(avg_v,1)) + " V (nominal 230V, deviation: " + str(round(abs(avg_v-230)/230*100,1)) + "%)\n"
            "- Average Frequency: " + str(round(avg_f,2)) + " Hz (nominal 50Hz, drift: " + str(round(abs(avg_f-50),2)) + " Hz)\n"
            "- Peak Demand: " + str(round(max_d,2)) + " kW\n\n"
            "Root Cause Analysis:\n"
            "The " + str(len(causes)) + " probable cause(s) were identified from telemetry trends "
            "across " + str(len(chunks)) + " retrieved incidents. The dominant fault signature indicates "
            + ("transformer stress and overload conditions" if top_status == "overload_risk" else "grid instability conditions")
            + " consistent with peak demand patterns.\n\n"
            "Severity: " + top_sev.upper() + " - Immediate operational attention recommended."
        )

        reasoning = (
            f"The hybrid retriever surfaced {len(chunks)} chunks matching the query. "
            f"Severity distribution: {dict(sev_counter)}. Top transformer status: "
            f"{top_status}. Recommendations are mapped from these dominant patterns."
        )

        confidence = round(
            min(0.95, 0.4 + 0.1 * len(chunks) + (0.1 if top_sev in ("high", "critical") else 0)),
            2,
        )
        return {
            "answer": answer,
            "root_causes": causes,
            "recommendations": recs,
            "confidence": confidence,
            "reasoning": reasoning,
        }


# ---------------------------------------------------------------------------
class OpenAIProvider:
    name = "openai"

    def __init__(self, settings: Settings):
        from langchain_openai import ChatOpenAI
        self.llm = ChatOpenAI(
            model=settings.llm_model,
            api_key=settings.openai_api_key,
            temperature=0.1,
            timeout=10,
        )

    def generate(self, query: str, chunks: List[RetrievedChunk]) -> Dict[str, Any]:
        from langchain_core.messages import HumanMessage, SystemMessage
        msgs = [
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=build_user_prompt(query, chunks)),
        ]
        resp = self.llm.invoke(msgs)
        return _extract_json(resp.content if hasattr(resp, "content") else str(resp))


class AnthropicProvider:
    name = "anthropic"

    def __init__(self, settings: Settings):
        from langchain_anthropic import ChatAnthropic
        self.llm = ChatAnthropic(
            model=settings.llm_model,
            api_key=settings.anthropic_api_key,
            temperature=0.1,
            timeout=10,
        )

    def generate(self, query: str, chunks: List[RetrievedChunk]) -> Dict[str, Any]:
        from langchain_core.messages import HumanMessage, SystemMessage
        msgs = [
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=build_user_prompt(query, chunks)),
        ]
        resp = self.llm.invoke(msgs)
        return _extract_json(resp.content if hasattr(resp, "content") else str(resp))



# ---------------------------------------------------------------------------
class GroqProvider:
    """Groq via its OpenAI-compatible REST API (httpx — no extra heavy deps)."""
    name = "groq"
    URL = "https://api.groq.com/openai/v1/chat/completions"

    def __init__(self, settings: Settings):
        # .strip() handles GROQ_API_KEY= gsk_... (leading space in .env)
        self.api_key = getattr(settings, "groq_api_key", "").strip()
        self.model   = (getattr(settings, "groq_model_large", "") or
                        getattr(settings, "groq_model", "") or
                        settings.llm_model or "llama-3.3-70b-versatile")

    def generate(self, query: str, chunks: List[RetrievedChunk]) -> Dict[str, Any]:
        import httpx
        # NOTE: no response_format=json_object — not all Groq models support it
        payload = {
            "model": self.model,
            "temperature": 0.1,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT + " Always respond with valid JSON only."},
                {"role": "user",   "content": build_user_prompt(query, chunks)},
            ],
        }
        headers = {"Authorization": f"Bearer {self.api_key}",
                   "Content-Type": "application/json"}
        with httpx.Client(timeout=10) as client:
            r = client.post(self.URL, json=payload, headers=headers)
            r.raise_for_status()
            content = r.json()["choices"][0]["message"]["content"]
        return _extract_json(content)


class GeminiProvider:
    """Google Gemini via the generativelanguage REST API (httpx)."""
    name = "gemini"

    def __init__(self, settings: Settings):
        self.api_key = settings.gemini_api_key
        self.model = settings.gemini_model

    def generate(self, query: str, chunks: List[RetrievedChunk]) -> Dict[str, Any]:
        import httpx
        url = (f"https://generativelanguage.googleapis.com/v1beta/models/"
               f"{self.model}:generateContent?key={self.api_key}")
        prompt = SYSTEM_PROMPT + "\n\n" + build_user_prompt(query, chunks)
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.1, "responseMimeType": "application/json"},
        }
        with httpx.Client(timeout=10) as client:
            r = client.post(url, json=payload)
            r.raise_for_status()
            content = r.json()["candidates"][0]["content"]["parts"][0]["text"]
        return _extract_json(content)


# ---------------------------------------------------------------------------
def get_provider(settings: Optional[Settings] = None):
    """Resolve provider per env. Falls back to TemplateProvider if API keys
    are missing or langchain imports fail."""
    settings = settings or get_settings()
    preferred = settings.llm_provider

    # Build an ordered candidate list: the configured provider first, then the
    # standard fallback chain Groq -> Gemini -> OpenAI -> Anthropic -> template.
    # A provider is only attempted if its API key is present.
    def _build(name):
        if name == "groq" and settings.groq_api_key:
            return GroqProvider(settings)
        if name == "gemini" and settings.gemini_api_key:
            return GeminiProvider(settings)
        if name == "openai" and settings.openai_api_key:
            return OpenAIProvider(settings)
        if name == "anthropic" and settings.anthropic_api_key:
            return AnthropicProvider(settings)
        if name == "template":
            return TemplateProvider()
        return None

    order = [preferred] + [p for p in ("groq", "gemini", "openai", "anthropic")
                           if p != preferred]
    for name in order:
        try:
            prov = _build(name)
            if prov is not None:
                if name != preferred:
                    logger.info("llm_provider_fallback", extra={"from": preferred, "to": name})
                return prov
        except Exception as exc:  # noqa: BLE001
            logger.warning("llm_provider_init_failed",
                           extra={"provider": name, "err": str(exc)})

    return TemplateProvider()
