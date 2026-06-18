"""
clean_thinkchat_duplicates.py — Limpia duplicados ThinkChat y deja solo el sync fresco.

Estrategia: DELETE todas las rows ThinkChat (origen='ThinkChat' o 'ThinkChat->Venta')
para que el próximo sync pueble el DW limpio desde el Excel (fuente de verdad).

Usage:
  python -m etl.clean_thinkchat_duplicates --dry-run
  python -m etl.clean_thinkchat_duplicates
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import psycopg2

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.core.config import settings  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("crm.etl.clean")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    pg_conn = psycopg2.connect(settings.DATABASE_URL_SYNC)
    cur = pg_conn.cursor()

    # 1) Count
    cur.execute("""
        SELECT
            classification_flags->>'origen_lead' AS origen,
            classification_flags->>'es_venta' AS es_venta,
            COUNT(*) AS total
        FROM crm.leads_unificados
        WHERE classification_flags->>'origen_lead' IN ('ThinkChat', 'ThinkChat->Venta')
        GROUP BY 1, 2
        ORDER BY 1, 2
    """)
    rows = cur.fetchall()
    total = sum(r[2] for r in rows)
    print(f"\n=== Pre-clean state ({total:,} total rows) ===")
    for r in rows:
        print(f"  {r[0]:25s}  es_venta={r[1]:1s}  {r[2]:>7,}")

    if args.dry_run:
        print("\nDRY RUN: nothing deleted")
    else:
        print(f"\n=== Deleting {total:,} ThinkChat rows ===")
        cur.execute("""
            DELETE FROM crm.leads_unificados
            WHERE classification_flags->>'origen_lead' IN ('ThinkChat', 'ThinkChat->Venta')
        """)
        deleted = cur.rowcount
        pg_conn.commit()
        print(f"Deleted {deleted:,} rows")

        # Verify
        cur.execute("""
            SELECT COUNT(*) FROM crm.leads_unificados
            WHERE classification_flags->>'origen_lead' IN ('ThinkChat', 'ThinkChat->Venta')
        """)
        remaining = cur.fetchone()[0]
        print(f"Remaining: {remaining:,}")

    pg_conn.close()


if __name__ == "__main__":
    main()
