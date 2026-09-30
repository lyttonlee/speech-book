"""Success envelope helper (docs §1.3)."""
from __future__ import annotations

import uuid


def ok(data=None) -> dict:
    return {"code": "OK", "data": data, "request_id": uuid.uuid4().hex[:12]}
