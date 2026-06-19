"""
CRM Unificado EPEM — ETL Worker
Stage 1 — Sync EPEM MySQL → PostgreSQL DW
"""

import logging
import re
from datetime import datetime
from typing import Optional

import os
import pymysql
import psycopg2
from psycopg2.extras import execute_values
from redis import Redis

from dotenv import load_dotenv
# Load .env from parent directory (etl -> backend -> crm-unificado)
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '..', '.env'))

from app.core.phone_norm import norm as phone_norm
from psycopg2.extras import Json

# Use localhost when running outside Docker
PG_HOST = os.getenv("POSTGRES_HOST", "postgres")
PG_PORT = os.getenv("POSTGRES_PORT", "5434")
PG_DB = os.getenv("POSTGRES_DB", "crm_epem")
PG_USER = os.getenv("POSTGRES_USER", "crm_admin")
PG_PASSWORD = os.getenv("POSTGRES_PASSWORD", "crm_secure_2026")
DATABASE_URL_SYNC = f"postgresql://{PG_USER}:{PG_PASSWORD}@{PG_HOST}:{PG_PORT}/{PG_DB}"

from app.core.config import settings

logger = logging.getLogger("crm.etl")


class EPEMSync:
    """Worker that syncs sales_opportunities from EPEM MySQL to PostgreSQL DW."""

    def __init__(self):
        self.pg_conn = psycopg2.connect(DATABASE_URL_SYNC)
        self.mysql_conn = pymysql.connect(
            host=settings.EPEM_DB_HOST,
            port=settings.EPEM_DB_PORT,
            user=settings.EPEM_DB_USER,
            password=settings.EPEM_DB_PASSWORD,
            database=settings.EPEM_DB_NAME,
            charset="utf8mb4",
        )
        self.redis_client: Optional[Redis] = None
        try:
            self.redis_client = Redis(
                host=settings.REDIS_HOST,
                port=settings.REDIS_PORT,
                socket_connect_timeout=3,
            )
            self.redis_client.ping()
        except Exception:
            logger.warning("Redis not available — proceeding without cache")

    # ── Phone Normalization ──────────────────────────────────────────

    @staticmethod
    def normalize_phone(phone: Optional[str]) -> Optional[str]:
        """Normalize phone to E.164-ish format: 595XXXXXXXXX."""
        if not phone or phone.strip() == "":
            return None
        cleaned = re.sub(r"[^\d+]", "", phone.strip())
        if cleaned.startswith("+"):
            cleaned = cleaned[1:]
        if cleaned.startswith("595"):
            return cleaned
        if len(cleaned) >= 9:
            return "595" + cleaned[-9:]
        return cleaned

    # ── Classification Flags ─────────────────────────────────────────

    @staticmethod
    def compute_classification_flags(row: dict) -> dict:
        """Compute all 9 classification flags for a lead.

        Regla de fuente (FASE 4, 10/06/2026):
        - Si epem_opportunity_id > 0 → Botmaker (viene de sales_opportunities, el bot de WhatsApp).
          El flag bm_customer_id / observation es solo metadata, no es la fuente.
        - Si epem_opportunity_id < 0 → ThinkChat (sintético del cruce con Excel ThinkChat).
        - Si epem_opportunity_id IS NULL → Manual (creado directamente por el equipo).

        Razon del fix: 30,920 ventas con status=15 estaban mal clasificadas como 'Manual'
        porque bm_customer_id era NULL — pero el lead SÍ venia de sales_opportunities.
        La fuente NO se determina por bm_customer_id, sino por la tabla de origen.
        """
        epem_opp_id = row.get("epem_opportunity_id")
        if epem_opp_id is not None and int(epem_opp_id) > 0:
            # Viene de sales_opportunities → Botmaker
            is_botmaker = 1
        elif epem_opp_id is not None and int(epem_opp_id) < 0:
            # ID sintetico → ThinkChat
            is_botmaker = 0
        else:
            # No viene de MySQL → Manual
            is_botmaker = 0

        # Metadata refinements (no afectan la fuente, solo flags de sub-tipo)
        is_pauta = 1 if is_botmaker and row.get("ad_id") and row["ad_id"] != "" else 0
        is_campana = 1 if is_botmaker and row.get("opportunity_campaign_id") is not None else 0

        # ThinkChat se determina por epem_opp_id < 0 (arriba), pero la logica legacy
        # sigue siendo util para casos donde la fila viene de sales_opportunities pero
        # tiene metadata ThinkChat (raro pero posible).
        is_thinkchat = 0 if is_botmaker else (
            1 if int(epem_opp_id or 0) < 0 else (
                1 if (row.get("ad_id") is not None and row["ad_id"] != "")
                     or (row.get("lead") and ("thinkchat" in str(row["lead"]).lower() or "thinkcomm" in str(row["lead"]).lower()))
                else 0
            )
        )
        is_manual = (
            1
            if not is_botmaker and not is_thinkchat and row.get("creator") in (1, 2) and row.get("chat_platform") is None
            else 0
        )
        is_regestion = 0
        now = datetime.now()
        if is_botmaker:
            created = row.get("created_at")
            if created and created.month < now.month:
                is_regestion = 1

        is_venta = 1 if row.get("status") in (13, 15) and row.get("contract_id") is not None else 0

        tipo_cartera = "Fria"
        created = row.get("created_at")
        if created and created.month == now.month and created.year == now.year:
            tipo_cartera = "Caliente"

        origen = "Otro"
        if is_botmaker:
            origen = "Botmaker"
        elif is_thinkchat:
            origen = "ThinkChat"
        elif is_manual:
            origen = "Manual"

        return {
            "es_botmaker": is_botmaker,
            "es_pauta": is_pauta,
            "es_campana": is_campana,
            "es_thinkchat": is_thinkchat,
            "es_manual": is_manual,
            "es_regestion": is_regestion,
            "es_venta": is_venta,
            "tipo_cartera": tipo_cartera,
            "unidad_negocio": "SIN ASIGNAR",  # pending WhatsApp line mapping
            "origen_lead": origen,
        }

    # ── Upsert Lead ──────────────────────────────────────────────────

    def upsert_lead(self, lead: dict) -> bool:
        """Insert or update a lead in leads_unificados."""
        sql = """
            INSERT INTO crm.leads_unificados (
                normalized_phone, fullname, email, enterprise_id, branch_id,
                sources, bm_customer_id, botmaker_observation, botmaker_chat_platform,
                ad_id, campaign_id, whatsapp_number, seller_id, closer_id,
                contract_id, status, creator, observation, lead,
                classification_flags, first_seen_at, last_updated_at,
                epem_opportunity_id
            ) VALUES (
                %(normalized_phone)s, %(fullname)s, %(email)s, %(enterprise_id)s, %(branch_id)s,
                %(sources)s, %(bm_customer_id)s, %(botmaker_observation)s, %(chat_platform)s,
                %(ad_id)s, %(campaign_id)s, %(whatsapp_number)s, %(seller_id)s, %(closer_id)s,
                %(contract_id)s, %(status)s, %(creator)s, %(observation)s, %(lead)s,
                %(classification_flags)s, %(first_seen_at)s, %(last_updated_at)s,
                %(epem_opportunity_id)s
            )
            ON CONFLICT (epem_opportunity_id) DO UPDATE SET
                normalized_phone = EXCLUDED.normalized_phone,
                fullname = EXCLUDED.fullname,
                email = EXCLUDED.email,
                sources = CASE
                    WHEN crm.leads_unificados.sources @> '["thinkchat"]'::jsonb
                      OR crm.leads_unificados.sources @> '["externo"]'::jsonb
                    THEN crm.leads_unificados.sources
                    ELSE EXCLUDED.sources
                END,
                bm_customer_id = EXCLUDED.bm_customer_id,
                botmaker_observation = EXCLUDED.botmaker_observation,
                botmaker_chat_platform = EXCLUDED.botmaker_chat_platform,
                ad_id = EXCLUDED.ad_id,
                campaign_id = EXCLUDED.campaign_id,
                whatsapp_number = EXCLUDED.whatsapp_number,
                seller_id = EXCLUDED.seller_id,
                closer_id = EXCLUDED.closer_id,
                contract_id = EXCLUDED.contract_id,
                status = EXCLUDED.status,
                creator = EXCLUDED.creator,
                observation = EXCLUDED.observation,
                lead = EXCLUDED.lead,
                classification_flags = EXCLUDED.classification_flags,
                last_updated_at = EXCLUDED.last_updated_at
        """
        try:
            with self.pg_conn.cursor() as cur:
                cur.execute(sql, lead)
            self.pg_conn.commit()
            return True
        except Exception as e:
            logger.error(f"Upsert failed for lead {lead.get('epem_opportunity_id')}: {e}")
            self.pg_conn.rollback()
            return False

    # ── Full Sync ────────────────────────────────────────────────────

    def sync(self, full: bool = False) -> dict:
        """Sync sales_opportunities from EPEM MySQL to PostgreSQL DW."""
        logger.info(f"Starting sync (full={full})")

        # Determine the last sync watermark
        # NOTA: so.updated_at es un INT corrupto (157049, 156843, etc) en MySQL — NO es timestamp.
        # Usamos so.id (monotonico) como watermark. Esto es seguro porque so.id es BIGINT auto-increment.
        #
        # Filtro de calidad: solo importar opportunities que sean:
        #   1. Botmaker (observation contiene "Botmaker")
        #   2. Ventas reales (contract_id > 0) — vengan de donde vengan
        #   3. Cargadas por SISTEMA (creator = 1) — carga automatica
        # Esto filtra las bases de telefono inyectadas manualmente por vendedores
        # (creators 2,3,4 con 0.02-4% conversion) que son ruido sin valor analitico.
        quality_filter = (
            "(so.observation LIKE '%Botmaker%' OR so.contract_id IS NOT NULL OR so.creator = 1)"
        )

        if full:
            where_clause = f"WHERE so.status != 30 AND {quality_filter}"
        else:
            with self.pg_conn.cursor() as cur:
                cur.execute("SELECT MAX(epem_opportunity_id) FROM crm.leads_unificados WHERE epem_opportunity_id > 0")
                last_id = cur.fetchone()[0]
            if last_id:
                where_clause = f"WHERE so.id > {int(last_id)} AND so.status != 30 AND {quality_filter}"
            else:
                where_clause = f"WHERE so.status != 30 AND {quality_filter}"

        # Fetch from EPEM MySQL
        query = f"""
            SELECT
                so.id AS epem_opportunity_id,
                so.phone,
                so.fullname,
                so.email,
                so.enterprise_id,
                so.branch_id,
                so.bm_customer_id,
                so.observation AS botmaker_observation,
                so.chat_platform,
                so.ad_id,
                so.opportunity_campaign_id AS campaign_id,
                so.whatsapp_number,
                so.seller_id,
                so.closer_id,
                so.contract_id,
                so.status,
                so.creator,
                so.observation,
                so.lead,
                so.created_at,
                so.updated_at
            FROM sales_opportunities so
            {where_clause}
            ORDER BY so.id
        """

        mysql_cur = self.mysql_conn.cursor(pymysql.cursors.DictCursor)
        mysql_cur.execute(query)

        upserted = 0
        skipped = 0
        batch = []
        batch_size = 1000

        now = datetime.now()

        for row in mysql_cur:
            # Phone normalization
            normalized_phone = self.normalize_phone(row["phone"])

            # Build sources (for MVP: botmaker or manual)
            is_botmaker = (
                row.get("observation") and "creado desde Botmaker" in str(row["observation"])
            ) or (row.get("bm_customer_id") is not None)
            sources = ["botmaker"] if is_botmaker else ["manual"]

            # Classification flags
            flags = self.compute_classification_flags(row)

            lead = {
                "epem_opportunity_id": row["epem_opportunity_id"],
                "normalized_phone": normalized_phone,
                "fullname": row["fullname"],
                "email": row.get("email"),
                "enterprise_id": row.get("enterprise_id"),
                "branch_id": row.get("branch_id"),
                "sources": psycopg2.extras.Json(sources),
                "bm_customer_id": row.get("bm_customer_id"),
                "botmaker_observation": row.get("botmaker_observation"),
                "chat_platform": row.get("chat_platform"),
                "ad_id": row.get("ad_id"),
                "campaign_id": row.get("campaign_id"),
                "whatsapp_number": row.get("whatsapp_number"),
                "seller_id": row.get("seller_id"),
                "closer_id": row.get("closer_id"),
                "contract_id": row.get("contract_id"),
                "status": row["status"],
                "creator": row.get("creator"),
                "observation": row.get("observation"),
                "lead": row.get("lead"),
                "classification_flags": psycopg2.extras.Json(flags),
                "first_seen_at": row.get("created_at", now),
                "last_updated_at": row.get("updated_at", now),
            }

            batch.append(lead)

            if len(batch) >= batch_size:
                self._flush_batch(batch)
                upserted += len(batch)
                batch = []
                logger.info(f"  Synced {upserted} records...")

        # Final flush
        if batch:
            self._flush_batch(batch)
            upserted += len(batch)

        mysql_cur.close()

        # Log sync
        result = {
            "source": "botmaker" if not full else "full_initial",
            "records_upserted": upserted,
            "records_skipped": skipped,
            "started_at": now.isoformat(),
            "completed_at": datetime.now().isoformat(),
        }

        try:
            with self.pg_conn.cursor() as cur:
                cur.execute(
                    """INSERT INTO crm.sync_log 
                       (source, records_upserted, records_skipped, started_at, completed_at)
                       VALUES (%(source)s, %(records_upserted)s, %(records_skipped)s, 
                               %(started_at)s, %(completed_at)s)""",
                    result,
                )
            self.pg_conn.commit()
        except Exception as e:
            logger.error(f"Failed to log sync: {e}")

        logger.info(f"Sync complete: {upserted} upserted, {skipped} skipped")
        return result

    def _flush_batch(self, batch: list):
        """Insert batch using individual upserts within a transaction."""
        import json
        sql = """
            INSERT INTO crm.leads_unificados (
                epem_opportunity_id, normalized_phone, fullname, email,
                enterprise_id, branch_id, sources, bm_customer_id,
                botmaker_observation, botmaker_chat_platform, ad_id,
                campaign_id, whatsapp_number, seller_id, closer_id,
                contract_id, status, creator, observation, lead,
                classification_flags, first_seen_at, last_updated_at
            ) VALUES (
                %(epem_opportunity_id)s, %(normalized_phone)s, %(fullname)s, %(email)s,
                %(enterprise_id)s, %(branch_id)s, %(sources)s::jsonb, %(bm_customer_id)s,
                %(botmaker_observation)s, %(chat_platform)s, %(ad_id)s,
                %(campaign_id)s, %(whatsapp_number)s, %(seller_id)s, %(closer_id)s,
                %(contract_id)s, %(status)s, %(creator)s, %(observation)s, %(lead)s,
                %(classification_flags)s::jsonb, %(first_seen_at)s, %(last_updated_at)s
            )
            ON CONFLICT (epem_opportunity_id) DO UPDATE SET
                normalized_phone = EXCLUDED.normalized_phone,
                fullname = EXCLUDED.fullname,
                email = EXCLUDED.email,
                sources = CASE
                    WHEN crm.leads_unificados.sources @> '["thinkchat"]'::jsonb
                      OR crm.leads_unificados.sources @> '["externo"]'::jsonb
                    THEN crm.leads_unificados.sources
                    ELSE EXCLUDED.sources
                END,
                bm_customer_id = EXCLUDED.bm_customer_id,
                botmaker_observation = EXCLUDED.botmaker_observation,
                botmaker_chat_platform = EXCLUDED.botmaker_chat_platform,
                ad_id = EXCLUDED.ad_id,
                campaign_id = EXCLUDED.campaign_id,
                whatsapp_number = EXCLUDED.whatsapp_number,
                seller_id = EXCLUDED.seller_id,
                closer_id = EXCLUDED.closer_id,
                contract_id = EXCLUDED.contract_id,
                status = EXCLUDED.status,
                creator = EXCLUDED.creator,
                observation = EXCLUDED.observation,
                lead = EXCLUDED.lead,
                classification_flags = EXCLUDED.classification_flags,
                last_updated_at = EXCLUDED.last_updated_at
        """
        try:
            with self.pg_conn.cursor() as cur:
                for lead in batch:
                    # Serialize JSONB fields as strings
                    lead_with_json = dict(lead)
                    lead_with_json["sources"] = json.dumps(lead["sources"].adapted)
                    lead_with_json["classification_flags"] = json.dumps(lead["classification_flags"].adapted)
                    # Savepoint por insert — si choca con idx_leads_contract_unique, no destruye el batch
                    cur.execute("SAVEPOINT incremental_sp")
                    try:
                        cur.execute(sql, lead_with_json)
                        cur.execute("RELEASE SAVEPOINT incremental_sp")
                    except psycopg2.IntegrityError:
                        cur.execute("ROLLBACK TO SAVEPOINT incremental_sp")
            self.pg_conn.commit()
        except Exception as e:
            logger.error(f"Batch insert failed: {e}")
            self.pg_conn.rollback()

    # ── Tracking Sync ────────────────────────────────────────────────

    def sync_trackings(self, full: bool = False) -> dict:
        """Sync sales_opportunity_trackings from EPEM MySQL to crm.lead_tracking."""
        logger.info(f"Starting tracking sync (full={full})")

        # Watermark: last synced tracking ID from source field
        if full:
            where_clause = ""
        else:
            with self.pg_conn.cursor() as cur:
                cur.execute(
                    """SELECT MAX(CAST(split_part(source, ':', 2) AS INTEGER))
                       FROM crm.lead_tracking WHERE source LIKE 'epem_tracking:%'"""
                )
                last_id = cur.fetchone()[0]
            if last_id:
                where_clause = f"WHERE sot.id > {int(last_id)}"
            else:
                where_clause = ""

        # Fetch trackings from EPEM MySQL
        query = f"""
            SELECT
                sot.id AS tracking_id,
                sot.sales_opportunity_id,
                sot.user_id AS seller_id,
                sot.created_at AS timestamp,
                sot.attended,
                sot.sold,
                sot.reject,
                sot.closer,
                sot.reassigned,
                sot.status AS tracking_status,
                sot.opportunity_status,
                sot.observation
            FROM sales_opportunity_trackings sot
            {where_clause}
            ORDER BY sot.id DESC
        """

        mysql_cur = self.mysql_conn.cursor(pymysql.cursors.DictCursor)
        mysql_cur.execute(query)

        upserted = 0
        skipped = 0
        batch = []
        batch_size = 500

        for row in mysql_cur:
            # Map sales_opportunity_id → lead UUID
            lead_id = self._get_lead_uuid(row["sales_opportunity_id"])
            if not lead_id:
                skipped += 1
                continue

            # Determine to_status
            to_status = self._infer_to_status(row)

            tracking = {
                "lead_id": lead_id,
                "from_status": None,  # would need window function over history
                "to_status": to_status,
                "seller_id": row["seller_id"],
                "timestamp": row["timestamp"],
                "source": f"epem_tracking:{row['tracking_id']}",
            }

            batch.append(tracking)

            if len(batch) >= batch_size:
                upserted += self._flush_tracking_batch(batch)
                batch = []
                logger.info(f"  Trackings synced: {upserted}...")

        if batch:
            upserted += self._flush_tracking_batch(batch)

        mysql_cur.close()

        result = {
            "trackings_upserted": upserted,
            "trackings_skipped": skipped,
        }
        logger.info(f"Tracking sync complete: {upserted} upserted, {skipped} skipped")
        return result

    def _get_lead_uuid(self, sales_opportunity_id: int) -> Optional[str]:
        """Map EPEM sales_opportunity_id to CRM lead UUID."""
        with self.pg_conn.cursor() as cur:
            cur.execute(
                "SELECT id FROM crm.leads_unificados WHERE epem_opportunity_id = %s",
                (sales_opportunity_id,)
            )
            row = cur.fetchone()
            return row[0] if row else None

    @staticmethod
    def _infer_to_status(row: dict) -> Optional[int]:
        """Infer the resulting opportunity status from tracking flags."""
        if row.get("sold") == 1:
            return 15  # Vendido
        if row.get("reject") == 1:
            return 30  # Descartado
        if row.get("opportunity_status") is not None:
            return int(row["opportunity_status"])
        if row.get("attended") == 1:
            return 5  # Contactado (mínimo: hubo interacción)
        return None

    def _flush_tracking_batch(self, batch: list) -> int:
        """Insert tracking batch with dedup by source. Returns actual inserts count."""
        sql = """
            INSERT INTO crm.lead_tracking (lead_id, from_status, to_status, seller_id, timestamp, source)
            VALUES (%(lead_id)s, %(from_status)s, %(to_status)s, %(seller_id)s, %(timestamp)s, %(source)s)
            ON CONFLICT DO NOTHING
        """
        inserted = 0
        try:
            with self.pg_conn.cursor() as cur:
                for t in batch:
                    cur.execute(sql, t)
                    inserted += cur.rowcount
            self.pg_conn.commit()
        except Exception as e:
            logger.error(f"Tracking batch insert failed: {e}")
            self.pg_conn.rollback()
        return inserted

    def close(self):
        """Clean up connections."""
        self.mysql_conn.close()
        self.pg_conn.close()
        if self.redis_client:
            self.redis_client.close()


def run_full_sync():
    """Entry point for initial migration."""
    syncer = EPEMSync()
    try:
        result = syncer.sync(full=True)
        logger.info(f"Full sync complete: {result}")
        # Also sync trackings
        tracking_result = syncer.sync_trackings(full=True)
        logger.info(f"Full tracking sync complete: {tracking_result}")
        result.update(tracking_result)
    finally:
        syncer.close()


def run_incremental_sync():
    """Entry point for periodic sync."""
    syncer = EPEMSync()
    try:
        result = syncer.sync(full=False)
        logger.info(f"Incremental sync complete: {result}")
        # Also sync trackings
        tracking_result = syncer.sync_trackings(full=False)
        logger.info(f"Incremental tracking sync complete: {tracking_result}")
        result.update(tracking_result)
        return result
    finally:
        syncer.close()


# ──────────────────────────────────────────────────────────────
# VENTAS EXTERNAS — Contracts de EPEM que no son ThinkChat ni Botmaker
# ──────────────────────────────────────────────────────────────

def run_externas_sync():
    """Importar contracts de EPEM que no matchearon con ThinkChat ni Botmaker.
    Estos son ventas que no vinieron por Meta Ads ni por Botmaker — walk-ins, referidos, etc.
    """
    import hashlib
    from datetime import datetime

    logger.info("Starting externas sync (contracts without ThinkChat/Botmaker match)")

    syncer = EPEMSync()
    try:
        # 1. Get all contract_ids already in the DW (from ThinkChat + Botmaker)
        with syncer.pg_conn.cursor() as cur:
            cur.execute("""
                SELECT DISTINCT contract_id FROM crm.leads_unificados
                WHERE contract_id IS NOT NULL AND contract_id > 0
            """)
            existing_contract_ids = set(r[0] for r in cur.fetchall())
        logger.info(f"Contracts already in DW: {len(existing_contract_ids)}")

        # 2. Fetch ALL contracts from EPEM
        mysql_cur = syncer.mysql_conn.cursor(pymysql.cursors.DictCursor)
        mysql_cur.execute("""
            SELECT
                con.id AS contract_id,
                con.enterprise_id,
                con.date AS contract_date,
                con.user_id AS seller_id,
                con.seller_supervisor_id AS supervisor_id,
                con.sales_closer_id AS closer_id,
                con.amount,
                cl.first_name,
                cl.last_name,
                cl.contact AS client_contact,
                pn.number AS phone_number
            FROM contracts con
            JOIN contract_clients cc ON con.id = cc.contract_id
            JOIN clients cl ON cc.client_id = cl.id
            LEFT JOIN phone_numbers pn ON cl.id = pn.client_id
            WHERE con.status IN (1, 2, 3, 5, 6)
              AND con.enterprise_id IN (1, 2, 3, 4, 5, 9, 14)
        """)

        # 3. Filter out contracts already in DW, keep only externas
        externas = []
        seen_contracts = set()
        for row in mysql_cur:
            cid = row["contract_id"]
            if cid in existing_contract_ids or cid in seen_contracts:
                continue
            seen_contracts.add(cid)
            phone_raw = row["phone_number"] or row["client_contact"]
            pn = phone_norm(phone_raw, fmt="intl") if phone_raw else None

            seed = f"externo|{cid}"
            epem_id = int(hashlib.md5(seed.encode()).hexdigest()[:8], 16) % 10_000_000

            fullname = f"{row['first_name'] or ''} {row['last_name'] or ''}".strip()[:500]
            if not fullname:
                fullname = "Sin nombre"

            externas.append({
                "contract_id": cid,
                "enterprise_id": row["enterprise_id"],
                "contract_date": row["contract_date"],
                "seller_id": row["seller_id"],
                "supervisor_id": row["supervisor_id"],
                "closer_id": row["closer_id"],
                "amount": row["amount"],
                "phone": pn,
                "fullname": fullname,
                "epem_id": epem_id,
            })
        mysql_cur.close()

        logger.info(f"Externas to import: {len(externas)}")

        # 4. Insert externas into DW
        sql = """
            INSERT INTO crm.leads_unificados (
                normalized_phone, fullname, email, enterprise_id, sources,
                observation, ad_id, whatsapp_number, seller_id, closer_id, supervisor_id, contract_id,
                status, classification_flags,
                first_seen_at, last_updated_at, contract_date, amount, epem_opportunity_id
            ) VALUES (
                %(normalized_phone)s, %(fullname)s, %(email)s, %(enterprise_id)s, %(sources)s::jsonb,
                %(observation)s, %(ad_id)s, %(whatsapp_number)s, %(seller_id)s, %(closer_id)s, %(supervisor_id)s, %(contract_id)s,
                %(status)s, %(classification_flags)s::jsonb,
                %(first_seen_at)s, %(last_updated_at)s, %(contract_date)s, %(amount)s,
                %(epem_opportunity_id)s
            )
            ON CONFLICT (epem_opportunity_id) DO UPDATE SET
                normalized_phone = EXCLUDED.normalized_phone,
                fullname = EXCLUDED.fullname,
                contract_id = EXCLUDED.contract_id,
                status = EXCLUDED.status,
                seller_id = EXCLUDED.seller_id,
                closer_id = COALESCE(EXCLUDED.closer_id, crm.leads_unificados.closer_id),
                supervisor_id = COALESCE(EXCLUDED.supervisor_id, crm.leads_unificados.supervisor_id),
                amount = COALESCE(EXCLUDED.amount, crm.leads_unificados.amount),
                classification_flags = EXCLUDED.classification_flags,
                last_updated_at = EXCLUDED.last_updated_at,
                contract_date = COALESCE(EXCLUDED.contract_date, crm.leads_unificados.contract_date)
        """

        batch_size = 500
        upserted = 0
        for i in range(0, len(externas), batch_size):
            batch = externas[i:i+batch_size]
            params_batch = []
            for ext in batch:
                flags = {
                    "es_botmaker": 0, "es_pauta": 0, "es_campana": 0,
                    "es_thinkchat": 0, "es_manual": 0, "es_regestion": 0,
                    "es_venta": 1, "tipo_cartera": "Externa",
                    "unidad_negocio": "", "origen_lead": "Externo",
                    "epem_contract_id_real": str(ext["contract_id"]),
                }
                params_batch.append({
                    "normalized_phone": ext["phone"] or "",
                    "fullname": ext["fullname"],
                    "email": None,
                    "enterprise_id": ext["enterprise_id"],
                    "sources": Json(["externo"]),
                    "observation": "",
                    "ad_id": "",
                    "whatsapp_number": ext["phone"] or "",
                    "seller_id": ext["seller_id"],
                    "closer_id": ext["closer_id"],
                    "supervisor_id": ext["supervisor_id"],
                    "contract_id": ext["contract_id"],
                    "status": 15,
                    "classification_flags": Json(flags),
                    "first_seen_at": ext["contract_date"],
                    "last_updated_at": ext["contract_date"],
                    "contract_date": ext["contract_date"],
                    "amount": ext["amount"],
                    "epem_opportunity_id": ext["epem_id"],
                })

            try:
                with syncer.pg_conn.cursor() as cur:
                    for p in params_batch:
                        cur.execute(sql, p)
                syncer.pg_conn.commit()
                upserted += len(batch)
                logger.info(f"  Externas synced: {upserted}...")
            except Exception as e:
                logger.error(f"Batch insert failed: {e}")
                syncer.pg_conn.rollback()

        logger.info(f"Externas sync complete: {upserted} upserted")
        return {"externas_upserted": upserted}

    finally:
        syncer.close()
