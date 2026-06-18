"""
retag_thinkchat_ventas.py — Re-tag leads ThinkChat ya en el DW con flag es_venta.

FASE 3 (10/06/2026): Para los 94,337 leads ya insertados con origen='ThinkChat',
corre el mismo cruce MySQL que el sync y marca:
  - es_venta=1, origen='ThinkChat->Venta' para los que matchearon con contract
  - (los que NO matchearon quedan como están)

Uso:
  python -m etl.retag_thinkchat_ventas --dry-run
  python -m etl.retag_thinkchat_ventas
  python -m etl.retag_thinkchat_ventas --batch-size 5000
"""
from __future__ import annotations

import argparse
import logging
import sys
from datetime import datetime
from pathlib import Path

import psycopg2
import pymysql

# Path fix para imports cuando se corre como script
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.config import settings  # noqa: E402
from app.core.phone_norm import norm as phone_norm  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("crm.etl.retag")


def fetch_venta_phones(date_from: str, date_to: str) -> tuple[set[str], dict[str, int]]:
    """
    Mismo cruce que ThinkChatSync._fetch_venta_phones (regla dash_core.py).
    Devuelve (set de phones, dict phone -> contract_id).
    """
    epem = {
        "host": settings.EPEM_DB_HOST,
        "port": int(settings.EPEM_DB_PORT),
        "user": settings.EPEM_DB_USER,
        "password": settings.EPEM_DB_PASSWORD,
        "database": settings.EPEM_DB_NAME,
    }
    sql = """
    SELECT
        con.id AS contract_id,
        pn.number AS phone_number,
        cl.contact AS client_contact
    FROM contracts con
    JOIN contract_clients cc ON con.id = cc.contract_id
    JOIN clients cl ON cc.client_id = cl.id
    LEFT JOIN phone_numbers pn ON cl.id = pn.client_id
    WHERE con.status IN (1, 2, 3, 5, 6)
      AND con.request_financing_number IS NULL
      AND con.enterprise_id IN (1, 2, 5)
      AND con.date >= %s
      AND con.date <= %s
    """
    phones: set[str] = set()
    contract_map: dict[str, int] = {}
    with pymysql.connect(**epem, connect_timeout=10, cursorclass=pymysql.cursors.SSCursor) as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (date_from, date_to))
            for row in cur:
                contract_id, phone_number, client_contact = row
                phone_to_norm = phone_number or client_contact
                pn = phone_norm(phone_to_norm, fmt="intl")
                if pn and pn not in contract_map:
                    contract_map[pn] = contract_id
                    phones.add(pn)
    return phones, contract_map


def get_date_range_pg(pg_conn) -> tuple[str, str]:
    """Obtiene min/max first_seen_at de los ThinkChat actuales."""
    with pg_conn.cursor() as cur:
        cur.execute("""
            SELECT
                MIN(first_seen_at)::date AS min_d,
                MAX(first_seen_at)::date AS max_d,
                COUNT(*) AS total
            FROM crm.leads_unificados
            WHERE classification_flags->>'origen_lead' IN ('ThinkChat', 'ThinkChat->Venta')
        """)
        row = cur.fetchone()
        return row[0].isoformat() if row[0] else "2020-01-01", row[1].isoformat() if row[1] else "2026-12-31", row[2]


def retag_dry_run(pg_conn, venta_phones: set[str], contract_map: dict[str, int]) -> dict:
    """Cuenta cuantos leads serían re-etiquetados."""
    with pg_conn.cursor() as cur:
        # Total ThinkChat actuales
        cur.execute("""
            SELECT COUNT(*) FROM crm.leads_unificados
            WHERE classification_flags->>'origen_lead' = 'ThinkChat'
        """)
        total_thinkchat = cur.fetchone()[0]

        # Cuantos matchearían con ventas
        cur.execute("""
            SELECT COUNT(*) FROM crm.leads_unificados
            WHERE classification_flags->>'origen_lead' = 'ThinkChat'
              AND normalized_phone = ANY(%s)
        """, (list(venta_phones),))
        match_count = cur.fetchone()[0]

    return {
        "total_thinkchat_current": total_thinkchat,
        "match_count": match_count,
        "no_match_count": total_thinkchat - match_count,
        "venta_phones_total": len(venta_phones),
    }


def retag_execute(pg_conn, venta_phones: set[str], contract_map: dict[str, int], batch_size: int = 5000) -> dict:
    """
    UPDATE en batches. Cambia origen_lead y es_venta para los que matchean.
    El epem_opportunity_id se setea al ID real del contrato.
    """
    if not venta_phones:
        logger.warning("No venta phones fetched, nothing to retag")
        return {"updated": 0, "batches": 0}

    venta_list = list(venta_phones)
    total_updated = 0
    batches = 0

    with pg_conn.cursor() as cur:
        # Procesar por chunks para no cargar todo en memoria
        for i in range(0, len(venta_list), batch_size):
            chunk = venta_list[i:i + batch_size]
            # UPDATE con jsonb_set para los dos flags
            cur.execute("""
                UPDATE crm.leads_unificados
                SET
                    classification_flags = jsonb_set(
                        jsonb_set(
                            classification_flags,
                            '{es_venta}',
                            '1'::jsonb
                        ),
                        '{origen_lead}',
                        '"ThinkChat->Venta"'::jsonb
                    ),
                    last_updated_at = NOW()
                WHERE classification_flags->>'origen_lead' = 'ThinkChat'
                  AND normalized_phone = ANY(%s)
            """, (chunk,))
            total_updated += cur.rowcount
            batches += 1
            logger.info(f"Batch {batches}: {cur.rowcount} rows updated")

        # Ahora: guardar el contract_id real en classification_flags (sin tocar epem_opportunity_id)
        # Razon: epem_opportunity_id es UNIQUE en la tabla, y el contract_id real puede estar
        # duplicado (multiples rows ThinkChat matchearon al mismo contrato). El flag
        # 'epem_contract_id_real' en jsonb es la referencia para BI/auditoria.
        logger.info("Saving real contract_id to classification_flags...")
        cur.execute("""
            SELECT id, normalized_phone
            FROM crm.leads_unificados
            WHERE classification_flags->>'origen_lead' = 'ThinkChat->Venta'
              AND classification_flags->>'epem_contract_id_real' IS NULL
        """)
        rows = cur.fetchall()
        logger.info(f"Found {len(rows)} rows to enrich with epem_contract_id_real")
        id_updates = 0
        for row in rows:
            row_id, phone = row
            contract_id = contract_map.get(phone)
            if contract_id:
                cur.execute("""
                    UPDATE crm.leads_unificados
                    SET classification_flags = jsonb_set(
                        classification_flags,
                        '{epem_contract_id_real}',
                        %s::text::jsonb
                    )
                    WHERE id = %s
                """, (str(contract_id), row_id))
                id_updates += 1
        logger.info(f"Enriched {id_updates} rows with epem_contract_id_real flag")

    pg_conn.commit()
    return {"updated": total_updated, "batches": batches, "id_updates": id_updates}


def main():
    parser = argparse.ArgumentParser(description="Re-tag ThinkChat leads with es_venta flag")
    parser.add_argument("--dry-run", action="store_true", help="Only count, don't UPDATE")
    parser.add_argument("--batch-size", type=int, default=5000, help="Phones per batch UPDATE")
    args = parser.parse_args()

    logger.info(f"=== retag_thinkchat_ventas dry_run={args.dry_run} ===")

    # 1) Conectar a Postgres
    pg_conn = psycopg2.connect(settings.DATABASE_URL_SYNC)

    # 2) Obtener rango de fechas del DW
    min_d, max_d, total = get_date_range_pg(pg_conn)
    logger.info(f"DW ThinkChat range: {min_d} -> {max_d} ({total:,} rows)")

    # 3) Fetch phones de EPEM
    logger.info(f"Fetching venta phones from EPEM ({min_d} -> {max_d})...")
    venta_phones, contract_map = fetch_venta_phones(min_d, max_d)
    logger.info(f"EPEM has {len(venta_phones):,} unique phones with confirmed contracts")

    # 4) Dry-run o execute
    if args.dry_run:
        result = retag_dry_run(pg_conn, venta_phones, contract_map)
        logger.info(f"DRY RUN: {result}")
        print("\n=== DRY RUN RESULT ===")
        for k, v in result.items():
            print(f"  {k}: {v:,}" if isinstance(v, int) else f"  {k}: {v}")
    else:
        result = retag_execute(pg_conn, venta_phones, contract_map, batch_size=args.batch_size)
        logger.info(f"RETAG: {result}")
        print("\n=== RETAG RESULT ===")
        for k, v in result.items():
            print(f"  {k}: {v:,}" if isinstance(v, int) else f"  {k}: {v}")

    pg_conn.close()
    logger.info("Done.")


if __name__ == "__main__":
    main()
