"""
backfill_botmaker_ventas.py — Re-clasifica leads que vienen de sales_opportunities
(epem_opportunity_id > 0) pero estaban mal clasificados como 'Manual'.

Antes del fix: ~30,920 ventas con status=15 + es_venta=1 tenian origen='Manual' porque
el flag es_botmaker dependia de bm_customer_id / observation, no del origen del row.

Despues del fix: todo row con epem_opportunity_id > 0 es Botmaker por definicion.

Este script:
1. UPDATE masivo al DW: cambia origen_lead, es_botmaker para los rows mal clasificados
2. Loggea cuantos rows se actualizaron
"""
import sys
import logging
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import psycopg2
from app.core.config import settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("crm.etl.backfill")


def main():
    pg = psycopg2.connect(settings.DATABASE_URL_SYNC)
    cur = pg.cursor()

    # 1) Count
    cur.execute("""
        SELECT COUNT(*)
        FROM crm.leads_unificados
        WHERE epem_opportunity_id > 0
          AND (classification_flags->>'es_botmaker')::int = 0
    """)
    candidates = cur.fetchone()[0]
    logger.info(f"Candidatos a re-clasificar: {candidates:,}")

    if candidates == 0:
        logger.info("Nada que hacer.")
        pg.close()
        return

    # 2) Dry-run first: cuantas se actualizarian?
    cur.execute("""
        SELECT
            classification_flags->>'origen_lead' AS origen_actual,
            COUNT(*) AS total
        FROM crm.leads_unificados
        WHERE epem_opportunity_id > 0
          AND (classification_flags->>'es_botmaker')::int = 0
        GROUP BY 1
        ORDER BY 2 DESC
    """)
    print("\n=== Distribucion pre-backfill ===")
    for r in cur.fetchall():
        print(f"  origen={r[0] or 'NULL':25s}  total={r[1]:,}")

    # 3) UPDATE masivo: cambiar origen_lead a 'Botmaker' y es_botmaker=1
    logger.info("Ejecutando UPDATE masivo...")
    cur.execute("""
        UPDATE crm.leads_unificados
        SET classification_flags = jsonb_set(
            jsonb_set(
                classification_flags,
                '{es_botmaker}',
                '1'::jsonb
            ),
            '{origen_lead}',
            '"Botmaker"'::jsonb
        )
        WHERE epem_opportunity_id > 0
          AND (classification_flags->>'es_botmaker')::int = 0
    """)
    updated = cur.rowcount
    pg.commit()
    logger.info(f"  Updated {updated:,} rows")

    # 4) Verificar
    cur.execute("""
        SELECT
            classification_flags->>'origen_lead' AS origen,
            (classification_flags->>'es_botmaker')::int AS es_bm,
            (classification_flags->>'es_venta')::int AS es_v,
            COUNT(*) AS total
        FROM crm.leads_unificados
        WHERE epem_opportunity_id > 0
        GROUP BY 1, 2, 3
        ORDER BY 4 DESC
        LIMIT 10
    """)
    print("\n=== Post-backfill (top 10) ===")
    for r in cur.fetchall():
        print(f"  origen={r[0]:25s}  es_bm={r[1]}  es_v={r[2]}  total={r[3]:,}")

    pg.close()


if __name__ == "__main__":
    main()
