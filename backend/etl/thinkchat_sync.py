"""
CRM Unificado EPEM — ThinkChat ETL Worker
Phase 2 — Sync ThinkChat leads into PostgreSQL DW

Fuente principal: Excel autodescargado del portal ThinkChat (thinkchat_portal.py).
Las credenciales del portal vienen de TC_PORTAL_USER y TC_PORTAL_PASS en .env.

FASE 3 (10/06/2026): Cross-match con EPEM MySQL contracts (status=5, request_number=0)
para distinguir leads vs ventas. Regla copiada de lead_audit_engine.py:90-115.
"""
import hashlib
import json
import logging
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

import psycopg2
import pymysql
from psycopg2.extras import Json

from app.core.config import settings
from app.core.phone_norm import norm as phone_norm
from etl.thinkchat_portal import (
    ThinkChatPortalClient, PAUTAS_FILE, LoginFailed,
)
from etl.thinkchat_pautas_parser import parse_pautas_xlsx

logger = logging.getLogger("crm.etl.thinkchat")


class ThinkChatSync:
    """Worker that syncs ThinkChat leads to PostgreSQL DW."""

    def __init__(self):
        self.pg_conn = psycopg2.connect(settings.DATABASE_URL_SYNC)
        self._venta_phones_cache: Optional[set[str]] = None

    @staticmethod
    def normalize_phone(phone: Optional[str]) -> Optional[str]:
        """Compat: usa phone_norm intl de app.core.phone_norm."""
        return phone_norm(phone, fmt="intl")

    def _fetch_venta_phones(self, date_from: str, date_to: str) -> set[str]:
        """
        Cruza con EPEM MySQL contracts para identificar leads que terminaron en venta.
        Regla copiada literal de C:\\thinkchat_dashboard\\dash_core.py:197-227
        (NO lead_audit_engine.py — esa es la regla estricta del audit, distinta del dashboard).

        Reglas:
          - c.date BETWEEN :df AND :dt
          - c.enterprise_id IN (1, 2, 3, 4, 5, 9, 14)
          - c.status IN (1, 2, 3, 5, 6)  -- cualquier no-cancelado, NO solo =5
          - LEFT JOIN phone_numbers pn — usa pn.number, no cl.contact

        CRM-FIX-5: Ahora guarda TODOS los contracts por phone (1:N), no solo el primero.
        El matching por cercania temporal se hace en sync_from_excel.
        """
        if self._venta_phones_cache is not None:
            return self._venta_phones_cache

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
            con.enterprise_id,
            con.date AS contract_date,
            con.user_id AS seller_id,
            pn.number AS phone_number,
            cl.contact AS client_contact
        FROM contracts con
        JOIN contract_clients cc ON con.id = cc.contract_id
        JOIN clients cl ON cc.client_id = cl.id
        LEFT JOIN phone_numbers pn ON cl.id = pn.client_id
        WHERE con.status IN (1, 2, 3, 5, 6)
          AND con.enterprise_id IN (1, 2, 3, 4, 5, 9, 14)
          AND con.date >= %s
          AND con.date <= %s
        """

        phones: set[str] = set()
        # CRM-FIX-5: dict phone → lista de contracts (1:N)
        contracts_by_phone: dict[str, list[dict]] = {}
        try:
            with pymysql.connect(**epem, connect_timeout=10, cursorclass=pymysql.cursors.SSCursor) as conn:
                with conn.cursor() as cur:
                    cur.execute(sql, (date_from, date_to))
                    for row in cur:
                        contract_id, enterprise_id, contract_date, seller_id, phone_number, client_contact = row
                        phone_to_norm = phone_number or client_contact
                        pn = phone_norm(phone_to_norm, fmt="intl")
                        if pn:
                            if pn not in contracts_by_phone:
                                contracts_by_phone[pn] = []
                            # Evitar duplicados exactos (mismo contract_id + phone)
                            existing_ids = {c["contract_id"] for c in contracts_by_phone[pn]}
                            if contract_id not in existing_ids:
                                contracts_by_phone[pn].append({
                                    "contract_id": contract_id,
                                    "enterprise_id": enterprise_id,
                                    "contract_date": str(contract_date) if contract_date else None,
                                    "seller_id": seller_id if seller_id else None,
                                })
                            phones.add(pn)
            self._venta_phones_cache = phones
            self._contracts_by_phone_cache = contracts_by_phone
            # Mantener caches legacy para compatibilidad (primer contract de cada phone)
            self._contract_map_cache = {pn: contracts[0]["contract_id"] for pn, contracts in contracts_by_phone.items()}
            self._contract_date_cache = {pn: contracts[0]["contract_date"] for pn, contracts in contracts_by_phone.items()}
            self._contract_seller_cache = {pn: contracts[0]["seller_id"] for pn, contracts in contracts_by_phone.items()}
            self._contract_enterprise_cache = {pn: contracts[0]["enterprise_id"] for pn, contracts in contracts_by_phone.items()}

            total_contracts = sum(len(v) for v in contracts_by_phone.values())
            multi = sum(1 for v in contracts_by_phone.values() if len(v) > 1)
            logger.info(
                f"Cross-match: {len(phones)} unique phones, {total_contracts} contracts "
                f"({multi} phones with multiple contracts), "
                f"status IN(1,2,3,5,6), enterprise IN(1,2,3,4,5,9,14), "
                f"{date_from} -> {date_to}"
            )
            return phones
        except Exception as e:
            logger.error(f"EPEM cross-match failed: {e}. Continuing without venta flag.")
            self._venta_phones_cache = set()
            self._contracts_by_phone_cache = {}
            self._contract_map_cache = {}
            return set()

    @staticmethod
    def _find_best_contract_match(
        contracts: list[dict],
        fecha_ingreso: datetime,
        max_lookback_days: int = 30,
        max_lookahead_days: int = 365,
    ) -> dict | None:
        """
        CRM-FIX-5: De una lista de contracts para un phone, elegir el mas cercano
        temporalmente al fecha_ingreso del lead.

        Logica:
          - Ventana valida: contract_date >= fecha_ingreso - max_lookback_days
                            AND contract_date <= fecha_ingreso + max_lookahead_days
          - Priorizar contracts DESPUES del lead (gente que compro despues de contactarse)
          - Si hay multiples en el futuro, elegir el mas cercano
          - Si no hay en el futuro, elegir el mas cercano en el pasado (regestion)
        """
        if not contracts:
            return None

        lookback_limit = fecha_ingreso - timedelta(days=max_lookback_days)
        lookahead_limit = fecha_ingreso + timedelta(days=max_lookahead_days)

        candidates = []
        for c in contracts:
            cd_str = c.get("contract_date")
            if not cd_str:
                continue
            try:
                cd = datetime.strptime(cd_str, "%Y-%m-%d")
            except (ValueError, TypeError):
                continue
            if lookback_limit <= cd <= lookahead_limit:
                candidates.append((c, cd))

        if not candidates:
            return None

        # Split: futuros (cd >= fecha_ingreso) vs pasados
        futuros = [(c, cd) for c, cd in candidates if cd >= fecha_ingreso]
        pasados = [(c, cd) for c, cd in candidates if cd < fecha_ingreso]

        if futuros:
            # Mas cercano despues del lead
            best = min(futuros, key=lambda x: x[1] - fecha_ingreso)
            return best[0]
        if pasados:
            # Mas cercano antes del lead (regestion)
            best = min(pasados, key=lambda x: fecha_ingreso - x[1])
            return best[0]
        return None

    def sync_from_excel(self, leads: list[dict]) -> dict:
        """
        Upsert ThinkChat leads parseados del Excel al DW.
        Cross-match con EPEM contracts status=5/req=0 para flag es_venta.
        """
        upserted = 0
        duplicates_skipped = 0
        errors = 0
        ventas_matcheadas = 0
        now = datetime.now()

        # 1) Calcular rango de fechas para el cruce MySQL
        # Razon: el cruce va por con.date (fecha del CONTRATO), no por first_seen_at.
        # Un lead de 2024 puede tener contrato de 2026 (frío). Usar un rango amplio.
        fechas_lead = [lead.get("fecha_ingreso") for lead in leads if lead.get("fecha_ingreso")]
        if fechas_lead:
            min_fecha_lead = min(fechas_lead).strftime("%Y-%m-%d")
        else:
            min_fecha_lead = "2020-01-01"
        # Restar 60 días para capturar leads anteriores a su primer registro
        from datetime import timedelta as _td
        min_fecha = (datetime.strptime(min_fecha_lead, "%Y-%m-%d") - _td(days=60)).strftime("%Y-%m-%d")
        max_fecha = now.strftime("%Y-%m-%d")

        # 2) Fetch phones con venta confirmada
        venta_phones = self._fetch_venta_phones(min_fecha, max_fecha)
        contracts_by_phone = getattr(self, "_contracts_by_phone_cache", {})

        # 3) SQL de UPSERT — mismo target epem_opportunity_id para idempotencia
        # IMPORTANTE: contract_id se guarda en la COLUMNA (no solo en jsonb) para que
        # las queries del dashboard que usan COUNT(DISTINCT contract_id) funcionen.
        # CRM-FIX: ThinkChat tiene prioridad sobre externo. Para ventas con contract_id,
        # se usa ON CONFLICT (contract_id) para reclamar el registro del externo.
        sql_lead = """
            INSERT INTO crm.leads_unificados (
                normalized_phone, fullname, email, enterprise_id,
                sources, botmaker_observation, ad_id, campaign_id,
                whatsapp_number, seller_id, contract_id,
                status, observation, lead, classification_flags,
                first_seen_at, last_updated_at, contract_date,
                epem_opportunity_id
            ) VALUES (
                %(normalized_phone)s, %(fullname)s, %(email)s, %(enterprise_id)s,
                %(sources)s::jsonb, %(observation)s, %(ad_id)s, NULL,
                 %(whatsapp_number)s, %(seller_id)s, %(contract_id)s,
                 %(status)s, %(observation)s, %(lead_label)s, %(classification_flags)s::jsonb,
                 %(first_seen_at)s, %(last_updated_at)s, %(contract_date)s,
                 %(epem_opportunity_id)s
            )
            ON CONFLICT (epem_opportunity_id) DO UPDATE SET
                normalized_phone = EXCLUDED.normalized_phone,
                fullname = EXCLUDED.fullname,
                enterprise_id = EXCLUDED.enterprise_id,
                sources = EXCLUDED.sources,
                botmaker_observation = EXCLUDED.botmaker_observation,
                ad_id = EXCLUDED.ad_id,
                whatsapp_number = EXCLUDED.whatsapp_number,
                contract_id = EXCLUDED.contract_id,
                status = EXCLUDED.status,
                classification_flags = EXCLUDED.classification_flags,
                last_updated_at = EXCLUDED.last_updated_at,
                contract_date = COALESCE(EXCLUDED.contract_date, crm.leads_unificados.contract_date)
        """

        # SQL para ventas: upsert por contract_id (ThinkChat tiene prioridad sobre externo)
        sql_venta = """
            INSERT INTO crm.leads_unificados (
                normalized_phone, fullname, email, enterprise_id,
                sources, botmaker_observation, ad_id, campaign_id,
                whatsapp_number, seller_id, contract_id,
                status, observation, lead, classification_flags,
                first_seen_at, last_updated_at, contract_date,
                epem_opportunity_id
            ) VALUES (
                %(normalized_phone)s, %(fullname)s, %(email)s, %(enterprise_id)s,
                %(sources)s::jsonb, %(observation)s, %(ad_id)s, NULL,
                 %(whatsapp_number)s, %(seller_id)s, %(contract_id)s,
                 %(status)s, %(observation)s, %(lead_label)s, %(classification_flags)s::jsonb,
                 %(first_seen_at)s, %(last_updated_at)s, %(contract_date)s,
                 %(epem_opportunity_id)s
            )
            ON CONFLICT (contract_id) WHERE contract_id > 0 DO UPDATE SET
                normalized_phone = EXCLUDED.normalized_phone,
                fullname = EXCLUDED.fullname,
                enterprise_id = EXCLUDED.enterprise_id,
                sources = EXCLUDED.sources,
                botmaker_observation = EXCLUDED.botmaker_observation,
                ad_id = EXCLUDED.ad_id,
                whatsapp_number = EXCLUDED.whatsapp_number,
                seller_id = EXCLUDED.seller_id,
                status = EXCLUDED.status,
                observation = EXCLUDED.observation,
                lead = EXCLUDED.lead,
                classification_flags = EXCLUDED.classification_flags,
                last_updated_at = EXCLUDED.last_updated_at,
                contract_date = COALESCE(EXCLUDED.contract_date, crm.leads_unificados.contract_date),
                epem_opportunity_id = EXCLUDED.epem_opportunity_id
        """

        with self.pg_conn.cursor() as cur:
            for lead in leads:
                phone = phone_norm(lead.get("phone"), fmt="intl")
                if not phone:
                    duplicates_skipped += 1
                    continue

                enterprise_id = lead.get("enterprise_id")
                fecha_ingreso = lead.get("fecha_ingreso", now)

                # 4) Cross-match: es venta? — CRM-FIX-5: matching por cercania temporal
                es_venta = phone in venta_phones
                contract_id_real = None
                contract_date_str = None
                seller_id_real = None
                if es_venta:
                    # Buscar el contract mas cercano a fecha_ingreso del lead
                    phone_contracts = contracts_by_phone.get(phone, [])
                    best = self._find_best_contract_match(phone_contracts, fecha_ingreso)
                    if best:
                        ventas_matcheadas += 1
                        contract_id_real = best["contract_id"]
                        contract_date_str = best["contract_date"]
                        seller_id_real = best["seller_id"]
                        # CRM-FIX-2: usar enterprise_id REAL del contract EPEM
                        if best["enterprise_id"] is not None:
                            enterprise_id = best["enterprise_id"]
                    else:
                        # Phone en venta_phones pero ningun contract en ventana temporal
                        es_venta = False

                if es_venta:
                    # epem_opportunity_id deterministico: MD5(phone|enterprise) → estable entre reinicios
                    seed = f"{phone}|{enterprise_id}"
                    epem_id = -(int(hashlib.md5(seed.encode()).hexdigest()[:8], 16) % 10_000_000)
                    origen = "ThinkChat->Venta"
                    lead_status = 15  # Vendido
                    # Usar fecha real del contrato como last_updated_at
                    if contract_date_str:
                        try:
                            venta_ts = datetime.strptime(contract_date_str, "%Y-%m-%d")
                        except ValueError:
                            venta_ts = now
                    else:
                        venta_ts = now
                else:
                    # Lead puro: ID deterministico basado en phone+enterprise
                    seed = f"{phone}|{enterprise_id}"
                    epem_id = -(int(hashlib.md5(seed.encode()).hexdigest()[:8], 16) % 10_000_000)
                    origen = "ThinkChat"
                    lead_status = 1  # Nuevo

                # Calcular tipo_cartera: Caliente si ingreso y venta en mismo mes/año
                if es_venta and contract_date_str:
                    try:
                        fecha_venta_dt = datetime.strptime(contract_date_str, "%Y-%m-%d")
                        mismo_mes = (fecha_ingreso.year == fecha_venta_dt.year and fecha_ingreso.month == fecha_venta_dt.month)
                        tipo_cartera = "Caliente" if mismo_mes else "Fria"
                    except ValueError:
                        tipo_cartera = "Caliente"
                else:
                    tipo_cartera = "Caliente"  # Lead sin venta = caliente (ThinkChat)

                flags = {
                    "es_botmaker": 0,
                    "es_pauta": 0,
                    "es_campana": 0,
                    "es_thinkchat": 1,
                    "es_manual": 0,
                    "es_regestion": 0,
                    "es_venta": 1 if es_venta else 0,
                    "tipo_cartera": tipo_cartera,
                    "unidad_negocio": lead.get("linea_raw", "SIN ASIGNAR"),
                    "origen_lead": origen,
                }
                if contract_id_real:
                    flags["epem_contract_id_real"] = str(contract_id_real)

                ad_id = lead.get("ad_id") or ""
                observation = lead.get("ultimo_estado") or ""
                canal = lead.get("canal") or ""
                if canal:
                    observation = f"[{canal}] {observation}".strip()

                params = {
                    "normalized_phone": phone,
                    "fullname": lead.get("fullname", "Sin nombre")[:500],
                    "email": None,
                    "enterprise_id": enterprise_id,
                    "sources": Json(["thinkchat"]),
                    "observation": observation[:2000] if observation else "",
                    "ad_id": ad_id,
                    "whatsapp_number": phone,
                    "seller_id": seller_id_real if es_venta else None,
                    "contract_id": contract_id_real if es_venta else None,
                    "status": lead_status,
                    "lead_label": f"{origen}: {lead.get('fullname', '')}"[:255],
                    "classification_flags": Json(flags),
                    "first_seen_at": fecha_ingreso,
                    "last_updated_at": venta_ts if es_venta else now,
                    "contract_date": venta_ts if es_venta else None,
                    "epem_opportunity_id": epem_id,
                }

                try:
                    cur.execute("SAVEPOINT thinkchat_sp")
                    # Ventas: upsert por contract_id (ThinkChat tiene prioridad sobre externo)
                    # Leads puros: upsert por epem_opportunity_id
                    cur.execute(sql_venta if es_venta else sql_lead, params)
                    cur.execute("RELEASE SAVEPOINT thinkchat_sp")
                    upserted += 1
                except psycopg2.IntegrityError as ie:
                    duplicates_skipped += 1
                    cur.execute("ROLLBACK TO SAVEPOINT thinkchat_sp")
                except Exception as e:
                    errors += 1
                    logger.error(f"Insert failed for {phone}: {e}")
                    cur.execute("ROLLBACK TO SAVEPOINT thinkchat_sp")

        self.pg_conn.commit()
        result = {
            "source": "thinkchat_excel",
            "records_upserted": upserted,
            "records_received": len(leads),
            "duplicates_skipped": duplicates_skipped,
            "errors": errors,
            "ventas_matcheadas": ventas_matcheadas,
            "leads_puros": upserted - ventas_matcheadas,
        }
        logger.info(
            f"ThinkChat sync: {upserted} upserted ({ventas_matcheadas} ventas, "
            f"{upserted - ventas_matcheadas} leads), {duplicates_skipped} duplicates, "
            f"{errors} errors, from {len(leads)} received"
        )
        return result

    def close(self):
        self.pg_conn.close()


def run_thinkchat_sync_from_excel(excel_path: Optional[Path] = None) -> dict:
    """
    Sync completo: lee el Excel (ya descargado) y upserts al DW.
    Si excel_path es None, usa PAUTAS_FILE del portal.
    Si el Excel no existe, intenta descargarlo.
    """
    started_at = datetime.now()
    excel_path = Path(excel_path) if excel_path else PAUTAS_FILE

    # 1) Si no existe el Excel, o tiene >1 día, intentar descargar
    # IMPORTANTE: no borrar el archivo hasta confirmar descarga exitosa
    re_download = False
    if not excel_path.exists():
        logger.info(f"Excel no existe en {excel_path}. Descargando...")
        re_download = True
    else:
        age_hours = (datetime.now() - datetime.fromtimestamp(excel_path.stat().st_mtime)).total_seconds() / 3600
        if age_hours > 24:
            logger.info(f"Excel tiene {age_hours:.0f}h de antigüedad. Intentando re-descarga...")
            re_download = True

    if re_download:
        try:
            client = ThinkChatPortalClient()
            new_path = client.download_yearly_pautas()
            client.close()
            excel_path = new_path
        except LoginFailed as e:
            logger.warning(f"Portal login failed: {e}. Usando Excel existente.")
            if not excel_path.exists():
                return {"source": "thinkchat", "status": "error", "error": f"Portal login failed and no cached Excel: {e}"}
        except Exception as e:
            logger.warning(f"Download failed: {e}. Usando Excel existente.")
            if not excel_path.exists():
                return {"source": "thinkchat", "status": "error", "error": f"Download failed and no cached Excel: {e}"}

    # 2) Parsear Excel — con retry si falla (XML corrupto del portal)
    MAX_PARSE_RETRIES = 2
    for parse_attempt in range(1, MAX_PARSE_RETRIES + 1):
        try:
            leads = parse_pautas_xlsx(excel_path)
            break
        except Exception as pe:
            logger.warning(f"Parse attempt {parse_attempt}/{MAX_PARSE_RETRIES} failed: {pe}")
            if parse_attempt < MAX_PARSE_RETRIES:
                logger.info("Re-descargando Excel por parseo corrupto...")
                try:
                    excel_path.unlink(missing_ok=True)
                    client = ThinkChatPortalClient()
                    excel_path = client.download_yearly_pautas()
                    client.close()
                except Exception as de:
                    logger.error(f"Re-download also failed: {de}")
                    return {"source": "thinkchat", "status": "error", "error": f"Parse failed and re-download also failed: {de}"}
            else:
                return {"source": "thinkchat", "status": "error", "error": f"Parse failed after {MAX_PARSE_RETRIES} attempts: {pe}"}

    if not leads:
        return {
            "source": "thinkchat_excel",
            "status": "error",
            "error": f"No leads parseados desde {excel_path}",
            "records_upserted": 0,
            "duration_sec": (datetime.now() - started_at).total_seconds(),
        }

    # 3) Upsert al DW (con cross-match)
    try:
        syncer = ThinkChatSync()
        result = syncer.sync_from_excel(leads)
        syncer.close()
        result["status"] = "ok"
        result["excel_path"] = str(excel_path)
        result["duration_sec"] = round((datetime.now() - started_at).total_seconds(), 2)
        return result
    except Exception as e:
        logger.error(f"ThinkChat sync error: {e}")
        return {"source": "thinkchat_excel", "status": "error", "error": str(e)}


# Mantener compatibilidad con scheduler viejo
def run_thinkchat_sync() -> dict:
    """Wrapper de compatibilidad. Llama al sync desde Excel."""
    return run_thinkchat_sync_from_excel()
