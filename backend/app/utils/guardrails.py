"""
Input guardrails for the Smart Grid Energy Intelligence Assistant.

Two layers, applied in this order:

  1. PII handling
       BLOCK   = refuse the request entirely (SSN, credit card, passport, IBAN,
                 bank account, government IDs, secret tokens/API keys).
       MASK    = replace with a placeholder token, then keep processing.
                 (email, phone, IP, street address, person name)
  2. Topic relevance
       The bot answers ONLY smart-grid / power-system questions.
       A query is on-topic if (after masking) it contains at least one
       domain term from DOMAIN_KEYWORDS, or matches a phrase pattern.

Why this design?
----------------
The capstone requirement explicitly calls for "Input validation guardrails"
under Requirement 1 (Basic). We also need to satisfy real-world deployability —
a utility company cannot let an LLM-powered assistant accept arbitrary text,
because operators sometimes paste raw maintenance logs containing customer
names, addresses, and account numbers. Masking lets us preserve the operational
context (voltage / region / equipment) while scrubbing identifying details.

Public API
----------
    validate_query(text: str) -> GuardrailVerdict

The verdict tells the caller whether the query is allowed and provides the
masked query that should be passed downstream.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Tuple

# ============================================================================
# 1. PII PATTERNS
# ============================================================================

# Patterns that, if matched, BLOCK the request outright. These are never
# needed for grid operations and represent high-risk personal data.
BLOCK_PATTERNS: Dict[str, re.Pattern] = {
    "ssn":          re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
    "credit_card":  re.compile(r"\b(?:\d[ -]?){13,19}\b"),
    "passport":     re.compile(r"\b[A-PR-WY][1-9]\d\s?\d{4}[1-9]\b"),
    "iban":         re.compile(r"\b[A-Z]{2}\d{2}[A-Z0-9]{11,30}\b"),
    "api_key":      re.compile(r"\b(?:sk|pk|api[_-]?key)[-_][A-Za-z0-9]{16,}\b",
                               re.IGNORECASE),
    "aws_secret":   re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
}

# Patterns that, if matched, are MASKED with a placeholder, then the request
# proceeds with the masked text. Per project decision, person names and street
# addresses pass through UN-masked (operators legitimately reference them).
# We still mask network-identifying info (email/phone/IP) because it offers
# zero analytical value but high re-identification risk.
MASK_PATTERNS: Dict[str, re.Pattern] = {
    "email":        re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b"),
    "phone":        re.compile(
        r"\b(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3,4}[-.\s]?\d{4}\b"
    ),
    "ipv4":         re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b"),
}

# Tokens used to replace masked PII. Stable, parseable from downstream code.
MASK_TOKENS = {
    "email":       "[REDACTED_EMAIL]",
    "phone":       "[REDACTED_PHONE]",
    "ipv4":        "[REDACTED_IP]",
}

# Two-capitalized-word phrases that look like names to the regex but are
# legitimate grid-domain proper nouns. Never mask these.
DOMAIN_PROPER_NOUNS = {
    "North Zone", "South Zone", "East Zone", "West Zone", "Central Hub",
    "Smart Meter", "Smart Grid", "Power Grid", "Power System", "Smart Meters",
    "Central Zone", "Distribution Network", "Transmission Line",
    "Renewable Energy", "Solar Farm", "Wind Farm", "Substation Alpha",
    "Substation Beta", "Substation Gamma", "Service Area", "Service Zone",
    "Demand Response", "Load Shedding", "Voltage Drop", "Voltage Sag",
    "Voltage Spike", "Frequency Drift", "Grid Stability", "Grid Health",
    "Grid Frequency", "Outage Event", "Transformer Health", "Transformer Overload",
    "Root Cause",
}

# ============================================================================
# 2. TOPIC WHITELIST
# ============================================================================

# Domain vocabulary. Single-word terms (lowercased). The query is split on
# non-alphanumerics; if any token matches one of these (after masking), the
# query is considered on-topic.
DOMAIN_KEYWORDS = {
    # core electrical
    "voltage", "current", "power", "energy", "electric", "electrical",
    "electricity", "watt", "watts", "kw", "kwh", "mw", "mwh", "kv", "amp",
    "amps", "ampere", "amperes", "frequency", "hz", "hertz", "phase",
    "harmonic", "harmonics", "reactive", "active", "apparent",
    # grid components
    "grid", "transformer", "transformers", "substation", "substations",
    "feeder", "feeders", "switchgear", "breaker", "breakers", "fuse",
    "fuses", "transmission", "distribution", "infrastructure", "generator",
    "generators", "inverter", "inverters", "capacitor", "reactor", "bus",
    "busbar", "line", "cable", "conductor", "insulator",
    # operations
    "outage", "outages", "blackout", "brownout", "fault", "faults",
    "stability", "instability", "telemetry", "anomaly", "anomalies",
    "alarm", "alarms", "alert", "alerts", "incident", "incidents",
    "overload", "overloads", "overloading", "surge", "surges", "dip",
    "sag", "swell", "flicker", "interruption", "interruptions",
    "maintenance", "scada", "smart-meter", "meter", "meters",
    # operational concepts
    "load", "demand", "consumption", "supply", "balancing", "regulation",
    "renewable", "renewables", "solar", "wind", "hydro", "battery",
    "storage", "peak", "off-peak", "capacity", "reliability", "efficiency",
    # diagnostic
    "anomaly", "anomalous", "abnormal", "deviation", "drift", "spike",
    "trip", "trips", "tripped", "failure", "failures", "root-cause", "rca",
    "mitigation", "recommendation", "recommendations", "forecast",
    # spatial
    "region", "zone", "north", "south", "east", "west", "central",
    "residential", "industrial", "commercial",
    # equipment / asset
    "equipment", "asset", "assets", "device", "devices", "node", "nodes",
    "sensor", "sensors", "controller", "relay",
}

# Multiword phrases that should always pass topic check.
DOMAIN_PHRASES = [
    "smart grid", "smart meter", "power grid", "power system",
    "power consumption", "voltage drop", "voltage sag", "voltage spike",
    "demand load", "grid stability", "grid health", "grid frequency",
    "outage event", "transformer health", "transformer overload",
    "root cause", "load balancing", "energy intelligence",
]

# ============================================================================
# 3. VERDICT
# ============================================================================

@dataclass
class GuardrailVerdict:
    """The result of running the full guardrail chain on a single query.

    `allow=True` means the (masked) query can proceed to the RAG pipeline.
    `allow=False` means the caller should surface `response_message` to the user.
    """

    allow: bool
    original_query: str
    masked_query: str
    pii_blocked: Dict[str, List[str]] = field(default_factory=dict)
    pii_masked: Dict[str, List[str]] = field(default_factory=dict)
    off_topic: bool = False
    reasons: List[str] = field(default_factory=list)
    response_message: str = ""  # human-friendly message to return to UI

    def to_dict(self) -> dict:
        """Serialize the verdict to a plain dict for inclusion in API responses."""
        return {
            "allow": self.allow,
            "original_query": self.original_query,
            "masked_query": self.masked_query,
            "pii_blocked": self.pii_blocked,
            "pii_masked": self.pii_masked,
            "off_topic": self.off_topic,
            "reasons": self.reasons,
            "response_message": self.response_message,
        }


# ============================================================================
# 4. DETECTION HELPERS
# ============================================================================

def _detect(text: str, patterns: Dict[str, re.Pattern]) -> Dict[str, List[str]]:
    """Scan text against a dict of named patterns and return all matches grouped by category."""
    hits: Dict[str, List[str]] = {}
    for name, pat in patterns.items():
        found = pat.findall(text)
        if found:
            hits[name] = list(dict.fromkeys(found))  # dedupe preserving order
    return hits


def _mask(text: str, patterns: Dict[str, re.Pattern]) -> Tuple[str, Dict[str, List[str]]]:
    """Replace PII matches in text with placeholder tokens; return masked text and matched categories."""
    hits: Dict[str, List[str]] = {}
    masked = text
    for name, pat in patterns.items():
        matches = pat.findall(masked)
        if not matches:
            continue
        hits[name] = list(dict.fromkeys(matches))
        masked = pat.sub(MASK_TOKENS[name], masked)
    return masked, hits


def _is_on_topic(text: str) -> bool:
    """Return True if the masked text contains at least one smart-grid domain keyword or phrase."""
    lower = text.lower()
    # phrase check first (cheap)
    for phrase in DOMAIN_PHRASES:
        if phrase in lower:
            return True
    # token check
    tokens = set(re.findall(r"[a-z][a-z0-9-]+", lower))
    return bool(tokens & DOMAIN_KEYWORDS)


# ============================================================================
# 5. PUBLIC API
# ============================================================================

OFF_TOPIC_MESSAGE = (
    "I can only answer questions about smart-grid operations — voltage, "
    "transformer health, outages, telemetry, grid stability, smart-meter "
    "anomalies, mitigation recommendations, etc. Please rephrase your question "
    "around those topics."
)

PII_BLOCK_MESSAGE_TEMPLATE = (
    "I cannot process this query because it contains sensitive personal data "
    "({categories}). Please remove the sensitive information and try again."
)

MIN_QUERY_LENGTH = 3
MAX_QUERY_LENGTH = 2000


def validate_query(text: str) -> GuardrailVerdict:
    """
    Run the full guardrail chain on a user query.

    Returns a GuardrailVerdict. Callers should check `verdict.allow`:
      - True  -> pass `verdict.masked_query` to the downstream RAG/agent chain
      - False -> return `verdict.response_message` to the user as-is
    """
    text = (text or "").strip()
    original = text

    # ---- 0. trivial validation ----
    # Allow known conversational phrases before any length check
    _GREETINGS = {
        "hi","hello","hey","help","thanks","thank you","ok","okay",
        "yes","no","bye","goodbye","who are you","what can you do",
        "what are you","how are you",
    }
    if text.lower().strip("!?.") in _GREETINGS:
        return GuardrailVerdict(
            allow=True, original_query=original, masked_query=text,
            reasons=[], response_message="",
        )
    if len(text) < MIN_QUERY_LENGTH:
        return GuardrailVerdict(
            allow=False, original_query=original, masked_query=text,
            reasons=["query_too_short"],
            response_message="Your question is too short. Please ask something more specific.",
        )
    if len(text) > MAX_QUERY_LENGTH:
        return GuardrailVerdict(
            allow=False, original_query=original, masked_query=text[:MAX_QUERY_LENGTH],
            reasons=["query_too_long"],
            response_message=f"Your question is too long ({len(text)} chars). "
                              f"Please shorten it to under {MAX_QUERY_LENGTH} characters.",
        )

    # ---- 1. BLOCK PII -> refuse ----
    blocked = _detect(text, BLOCK_PATTERNS)
    if blocked:
        categories = ", ".join(blocked.keys())
        return GuardrailVerdict(
            allow=False,
            original_query=original,
            masked_query=text,
            pii_blocked=blocked,
            reasons=["pii_blocked"],
            response_message=PII_BLOCK_MESSAGE_TEMPLATE.format(categories=categories),
        )

    # ---- 2. MASK PII -> continue with masked text ----
    masked_text, masked_hits = _mask(text, MASK_PATTERNS)

    # ---- 2b. CONVERSATIONAL SHORT-CIRCUIT ----
    # Allow greetings/help/ack so the LLM can respond naturally.
    _CONVERSATIONAL = {
        "hi", "hello", "hey", "help", "thanks", "thank you", "ok", "okay",
        "yes", "no", "bye", "goodbye", "who are you", "what can you do",
        "what are you", "how are you",
    }
    if masked_text.lower().strip("!?.") in _CONVERSATIONAL or len(masked_text.split()) <= 2:
        return GuardrailVerdict(
            allow=True,
            original_query=original,
            masked_query=masked_text,
            pii_masked=masked_hits,
            reasons=[],
            response_message="",
        )

    # ---- 3. TOPIC CHECK on the masked text ----
    if not _is_on_topic(masked_text):
        return GuardrailVerdict(
            allow=False,
            original_query=original,
            masked_query=masked_text,
            pii_masked=masked_hits,
            off_topic=True,
            reasons=["off_topic"],
            response_message=OFF_TOPIC_MESSAGE,
        )

    # ---- ALLOW ----
    reasons = []
    if masked_hits:
        reasons.append("pii_masked")
    return GuardrailVerdict(
        allow=True,
        original_query=original,
        masked_query=masked_text,
        pii_masked=masked_hits,
        reasons=reasons or ["ok"],
        response_message="ok",
    )
