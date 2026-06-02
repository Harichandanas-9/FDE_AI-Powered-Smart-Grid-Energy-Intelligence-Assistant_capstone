"""
Smoke test for multi-tenancy + JWT.

Exercises:
  - authenticate_user() for valid + invalid credentials
  - create_access_token() + decode_token() round-trip
  - tenant_id extraction from token payload
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(BACKEND_DIR))

from app.core.auth import authenticate_user, create_access_token, decode_token  # noqa: E402
from app.core.config import get_settings  # noqa: E402


def main() -> int:
    s = get_settings()

    print("[auth] demo users:", list(s.demo_users_dict.keys()))

    # 1) Bad password -> None
    assert authenticate_user("admin", "wrong", s) is None
    print("[auth] ✓ wrong password rejected")

    # 2) Unknown user -> None
    assert authenticate_user("nobody", "x", s) is None
    print("[auth] ✓ unknown user rejected")

    # 3) Valid login -> record
    user = authenticate_user("acme", "acme123", s)
    assert user and user["tenant_id"] == "acme"
    print(f"[auth] ✓ acme login -> tenant_id={user['tenant_id']}")

    # 4) Token round-trip
    tok = create_access_token(
        username=user["username"], tenant_id=user["tenant_id"],
        role=user["role"], settings=s,
    )
    assert "access_token" in tok
    decoded = decode_token(tok["access_token"], settings=s)
    assert decoded["tenant_id"] == "acme"
    assert decoded["sub"] == "acme"
    print(f"[auth] ✓ token round-trip: sub={decoded['sub']} tenant={decoded['tenant_id']}")

    # 5) Tampered token -> ValueError
    tampered = tok["access_token"][:-2] + "xx"
    try:
        decode_token(tampered, settings=s)
        print("[auth] ✗ tampered token NOT rejected")
        return 1
    except ValueError:
        print("[auth] ✓ tampered token rejected")

    print("\n[smoke] OK ✓")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
