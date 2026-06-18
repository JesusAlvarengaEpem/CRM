"""
backfill_botmaker_ventas.py — Re-sincroniza los leads Botmaker que en EPEM son ventas (status=15)
pero en el DW figuran como status=1 (porque se procesaron antes de la venta).

Estrategia:
1. Query a EPEM para obtener todos los sales_opportunities con status=15, contract_id IS NOT NULL
2. Verificar cuáles de esos epem_opportunity_id estan en el DW con status != 15 o contract_id IS NULL
3. DELETE esos del DW
4. Re-INSERTAR con el sync.py normal (que ya tiene el UPSERT correcto)
"""
import sys
import logging
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import psycopg2
import pymysql
from app.core.config import settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("crm.etl.backfill")


def main():
    # 1) EPEM: ventas con status=15 y contract_id IS NOT NULL
    epem = {
        "host": settings.EPEM_DB_HOST,
        "port": int(settings.EPEM_DB_PORT),
        "user": settings.EPEM_DB_USER,
        "password": settings.EPEM_DB_PASSWORD,
        "database": settings.EPEM_DB_NAME,
    }

    logger.info("Fetching ventas (status=15 + contract_id IS NOT NULL) from EPEM...")
    with pymysql.connect(**epem, cursorclass=pymysql.cursors.SSCursor) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT so.id
                FROM sales_opportunities so
                WHERE so.status = 15
                  AND so.contract_id IS NOT NULL
            """)
            venta_ids = [r[0] for r in cur.fetchall()]
    logger.info(f"  Found {len(venta_ids):,} ventas in EPEM")

    # 2) DW: cuales de esos estan en el DW pero con datos incorrectos (status != 15)
    pg = psycopg2.connect(settings.DATABASE_URL_SYNC)
    cur = pg.cursor()
    cur.execute("""
        SELECT epem_opportunity_id, status, contract_id,
               (classification_flags->>'es_venta')::int AS es_venta
        FROM crm.leads_unificados
        WHERE epem_opportunity_id = ANY(%s)
          AND (status != 15 OR contract_id IS NULL)
    """, (venta_ids,))
    incorrectas = cur.fetchall()
    logger.info(f"  {len(incorrectas):,} ventas en DW con status/contract_id incorrectos")

    if not incorrectas:
        logger.info("Nothing to backfill. Done.")
        pg.close()
        return

    # 3) DELETE esas rows para que el UPSERT las re-inserte
    incorrecta_ids = [r[0] for r in incorrectas]
    logger.info(f"  Deleting {len(incorrecta_ids):,} rows from DW...")
    cur.execute("""
        DELETE FROM crm.leads_unificados
        WHERE epem_opportunity_id = ANY(%s)
    """, (incorrecta_ids,))
    deleted = cur.rowcount
    pg.commit()
    logger.info(f"  Deleted {deleted:,} rows. Now the incremental sync will re-insert them correctly.")

    pg.close()


if __name__ == "__main__":
    main()
