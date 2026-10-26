"""Opaque, prefixed identifiers (e.g. `rec_3f9c…`)."""

from __future__ import annotations

import uuid


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:20]}"
