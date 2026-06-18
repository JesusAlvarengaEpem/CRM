"""
backfill_thinkchat_contract_id.py — Slice B
Copia classification_flags->>'epem_contract_id_real' a la columna contract_id
para que las queries del dashboard (que usan COUNT(DISTINCT contract_id))
puedan contar ventas ThinkChat correctamente.
"""
import sys
import logging
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import psycopg2
from app.core.config import settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("crm.etl.backfill_tc")


def main():
    pg = psycopg2.connect(settings.DATABASE_URL_SYNC)
    cur = pg.cursor()

    # 1) Count
    cur.execute("""
        SELECT COUNT(*)
        FROM crm.leads_unificados
        WHERE (classification_flags->>'es_venta')::int = 1
          AND SPLIT_PART(classification_flags->>'origen_lead', '->', 1) = 'ThinkChat'
          AND (classification_flags->>'epem_contract_id_real') IS NOT NULL
          AND contract_id IS NULL
    """)
    candidatos = cur.fetchone()[0]
    logger.info(f"Candidatos a backfill: {candidatos:,}")

    if candidatos == 0:
        logger.info("Nada que hacer.")
        pg.close()
        return

    # 2) UPDATE
    logger.info("Ejecutando UPDATE (cast epem_contract_id_real -> integer)...")
    cur.execute("""
        UPDATE crm.leads_unificados
        SET contract_id = (classification_flags->>'epem_contract_id_real')::integer
        WHERE (classification_flags->>'es_venta')::int = 1
          AND SPLIT_PART(classification_flags->>'origen_lead', '->', 1) = 'ThinkChat'
          AND (classification_flags->>'epem_contract_id_real') IS NOT NULL
          AND contract_id IS NULL
    """)
    updated = cur.rowcount
    pg.commit()
    logger.info(f"  Updated {updated:,} rows")

    # 3) Verify
    cur.execute("""
        SELECT
            COUNT(*) AS total_ventas,
            COUNT(DISTINCT contract_id) AS contratos_unicos,
            COUNT(*) FILTER (WHERE contract_id IS NULL) AS sin_contract
        FROM crm.leads_unificados
        WHERE (classification_flags->>'es_venta')::int = 1
          AND SPLIT_PART(classification_flags->>'origen_lead', '->', 1) = 'ThinkChat'
    """)
    total, contratos, sin = cur.fetchone()
    print(f"\n=== Post-backfill ===")
    print(f"  Total ventas ThinkChat: {total:,}")
    print(f"  Contratos unicos: {contratos:,}")
    print(f"  Sin contract_id: {sin:,}")

    pg.close()


if __name__ == "__main__":
    main()
