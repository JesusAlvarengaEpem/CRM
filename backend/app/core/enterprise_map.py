"""
enterprise_map.py — Enterprise/UN mapping (single source of truth) for CRM Unificado.

Copied verbatim from C:\\thinkchat_dashboard\\epem_shared.py:45-89.
Zero external dependencies. Imported by thinkchat_sync.py to map
ThinkChat Excel "Linea" column to enterprise_id.

RULE: Use this for ALL UN mapping in the CRM pipeline.
Never hardcode enterprise_id lookups locally.
"""
from __future__ import annotations


# ── Enterprise mapping (single source of truth) ──────────────────────────────

ENTERPRISE_MAP = {
    1: "ODONTOLOGIA",
    2: "MEDICINA PREPAGA",
    5: "MEDICINA ESTETICA",
}

ENTERPRISE_MAP_REVERSE = {v: k for k, v in ENTERPRISE_MAP.items()}

UNIDADES = ["MEDICINA ESTETICA", "MEDICINA PREPAGA", "ODONTOLOGIA"]

MESES = ["", "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
         "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]


# ── Unit name parsing (used by both pautas and formularios) ──────────────────

def parse_unidad_pauta(raw: str | None) -> str | None:
    """Parse a raw unit name from ThinkChat data into a normalized unit.

    Handles both Pautas format ('Odontologia', 'Epem', 'Medicina Estetica')
    and Formularios format ('Leads | Odontologia', 'Leads | Medicina Estética').

    Returns one of UNIDADES or None if unrecognized.
    """
    if not raw:
        return None

    UNIDAD_MAP = {
        "odontologia": "ODONTOLOGIA",
        "odontología": "ODONTOLOGIA",
        "medicina estetica": "MEDICINA ESTETICA",
        "medicina estética": "MEDICINA ESTETICA",
        "medicina prepaga": "MEDICINA PREPAGA",
        "epem": "MEDICINA ESTETICA",
        "estetica": "MEDICINA ESTETICA",
        "estética": "MEDICINA ESTETICA",
        "mpp": "MEDICINA PREPAGA",
    }

    # If format is "Leads | Odontologia", take the part after '|'
    clean = str(raw).strip()
    if "|" in clean:
        clean = clean.split("|")[-1].strip()

    return UNIDAD_MAP.get(clean.lower(), clean.upper() if clean else None)
