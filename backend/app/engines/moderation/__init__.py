"""Content moderation adapter (POC: pass-through).

Production plugs a real moderation service (docs §10.3). For the MVP scope we
keep a no-op that always passes so the POC chain runs without external deps.
"""
from __future__ import annotations


def check_text(text: str) -> tuple[bool, str | None]:
    """Return (ok, reason). POC always passes."""
    return True, None


def check_audio(_ref: str) -> tuple[bool, str | None]:
    return True, None
