"""
phone_norm.py — Phone normalization (single source of truth) for CRM Unificado.

Copied verbatim from C:\\thinkchat_dashboard\\epem_shared.py:17-40.
Zero external dependencies. Imported by thinkchat_sync.py for cross-match
with EPEM contracts (status=5, request_number=0).

RULE: Use this for ALL phone normalization in the CRM pipeline.
Never re-implement phone cleaning locally.
"""
from __future__ import annotations

import re


def norm(phone, fmt: str = "local") -> str | None:
    """Normalize a phone number.

    fmt="local" (default): 9-digit local format (595991234567 -> 991234567)
      Used for JOIN with phone_numbers.number in EPEM database.
    fmt="intl": 595-prefix international format (991234567 -> 595991234567)
      Used for lead audit engine cross-matches.

    Both formats are self-consistent: join local with local, or intl with intl.
    Never mix formats in a single JOIN.
    """
    if not phone or str(phone).strip() == "" or str(phone).lower() == "none":
        return None
    clean = re.sub(r"\D", "", str(phone))
    if clean.startswith("595"):
        clean = clean[3:]
    if clean.startswith("0"):
        clean = clean[1:]
    local = clean[-9:] if len(clean) >= 9 else (clean if clean else None)
    if local is None:
        return None
    if fmt == "intl":
        return "595" + local
    return local
