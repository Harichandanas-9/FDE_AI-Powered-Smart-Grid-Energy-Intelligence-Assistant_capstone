"""
Smoke test for the guardrails module.

Runs validate_query() against a representative set of queries:
  - ALLOWED (on-topic, no PII)
  - ALLOWED with masking (on-topic, but contains email / phone / name / address)
  - BLOCKED (PII like SSN / credit card)
  - REFUSED (off-topic — weather, sports, recipes)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(BACKEND_DIR))

from app.utils.guardrails import validate_query  # noqa: E402


TESTS = [
    # --- ALLOWED (clean) ---
    ("clean_grid_query",
     "Voltage instability is increasing in South Zone — what is the root cause?"),
    ("clean_transformer",
     "Transformer overload conditions are recurring during evening peak demand."),
    ("clean_meter",
     "Smart meter anomalies detected in a residential service area."),

    # --- ALLOWED (with masking) ---
    ("masked_email",
     "Voltage dip reported by operator at maria.smith@utility.com in North Zone."),
    ("masked_phone",
     "Engineer at +1-555-123-4567 flagged a transformer overload in West Zone."),
    ("masked_address",
     "Outage event reported at 1729 Maple Street affecting feeder F-12 voltage."),
    ("masked_name",
     "John Doe noticed grid frequency drop in Central Hub during peak demand."),

    # --- BLOCKED (high-risk PII) ---
    ("blocked_ssn",
     "My SSN is 123-45-6789 — please look up grid stability in my area."),
    ("blocked_credit_card",
     "Card 4111 1111 1111 1111 — investigate voltage anomalies."),

    # --- REFUSED (off-topic) ---
    ("off_topic_weather",
     "What is the weather in Bangalore today?"),
    ("off_topic_recipe",
     "How do I make pasta carbonara?"),
    ("off_topic_chitchat",
     "Tell me a joke."),

    # --- Edge cases ---
    ("too_short", "hi"),
    ("empty", ""),
]


def main() -> int:
    results = []
    for name, q in TESTS:
        v = validate_query(q)
        results.append((name, v))

    # Pretty-print summary
    print(f"{'NAME':<25} {'ALLOW':<6} {'REASONS':<30} MASKED?")
    print("-" * 95)
    for name, v in results:
        masked = ",".join(v.pii_masked.keys()) or "-"
        blocked = ",".join(v.pii_blocked.keys()) or ""
        reasons = ",".join(v.reasons) + (f" [blocked:{blocked}]" if blocked else "")
        print(f"{name:<25} {str(v.allow):<6} {reasons:<30} {masked}")

    # Detailed JSON for a few illustrative cases
    print("\n=== DETAIL: masked_email ===")
    for name, v in results:
        if name == "masked_email":
            print(json.dumps(v.to_dict(), indent=2))

    print("\n=== DETAIL: blocked_ssn ===")
    for name, v in results:
        if name == "blocked_ssn":
            print(json.dumps(v.to_dict(), indent=2))

    print("\n=== DETAIL: off_topic_weather ===")
    for name, v in results:
        if name == "off_topic_weather":
            print(json.dumps(v.to_dict(), indent=2))

    # Sanity assertions
    by_name = dict(results)
    assert by_name["clean_grid_query"].allow
    assert by_name["masked_email"].allow
    assert "email" in by_name["masked_email"].pii_masked
    assert not by_name["blocked_ssn"].allow
    assert "ssn" in by_name["blocked_ssn"].pii_blocked
    assert not by_name["off_topic_weather"].allow
    assert by_name["off_topic_weather"].off_topic
    assert not by_name["too_short"].allow
    print("\n[smoke] OK ✓")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
