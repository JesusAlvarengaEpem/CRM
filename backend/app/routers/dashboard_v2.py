"""
CRM Unificado EPEM — Dashboard Router (Enhanced)
Funnel secuencial + Campanas con nombres + Supervisores drill-down + Filtros
"""
from datetime import date, datetime, timedelta
from fastapi import APIRouter, Depends, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional

from app.core.database import get_db
from app.core.config import settings
from app.routers.auth import get_current_user

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])

# Campaign name cache (loaded lazily from EPEM MySQL)
_campaign_names: dict = {}
_un_names: dict = {1: "Odontologia", 2: "Med. Prepaga", 4: "Emergencias", 5: "Med. Estetica"}


def _load_campaign_names():
    """Load campaign names from EPEM MySQL into a cache dict."""
    global _campaign_names
    if _campaign_names:
        return _campaign_names
    try:
        import pymysql
        conn = pymysql.connect(
            host=settings.EPEM_DB_HOST, port=settings.EPEM_DB_PORT,
            user=settings.EPEM_DB_USER, password=settings.EPEM_DB_PASSWORD,
            database=settings.EPEM_DB_NAME, charset="utf8mb4", connect_timeout=10
        )
        cur = conn.cursor(pymysql.cursors.DictCursor)
        cur.execute("SELECT id, name FROM opportunity_campaigns ORDER BY id")
        _campaign_names = {row["id"]: row.get("name", f"Campana {row['id']}") for row in cur.fetchall()}
        cur.close(); conn.close()
        print(f"[CAMPAIGNS] Loaded {len(_campaign_names)} campaign names from EPEM")
    except Exception as e:
        print(f"[CAMPAIGNS] Failed to load: {e}")
        _campaign_names = {-1: f"Error: {e}"}
    return _campaign_names


def _build_filters(fecha_desde, fecha_hasta, enterprise_id, fuente, user=None):
    conditions = []
    params = {}
    if fecha_desde:
        conditions.append("first_seen_at >= :fecha_desde")
        params["fecha_desde"] = fecha_desde
    if fecha_hasta:
        conditions.append("first_seen_at <= :fecha_hasta")
        d = datetime.strptime(fecha_hasta, "%Y-%m-%d") + timedelta(days=1)
        params["fecha_hasta"] = d.strftime("%Y-%m-%d")
    if enterprise_id:
        conditions.append("enterprise_id = :enterprise_id")
        params["enterprise_id"] = enterprise_id
    if fuente:
        conditions.append("(classification_flags->>'origen_lead') = :fuente")
        params["fuente"] = fuente
    if user:
        if user.get("role") == "vendedor" and user.get("seller_id"):
            conditions.append("seller_id = :seller_id")
            params["seller_id"] = user["seller_id"]
        elif user.get("role") == "supervisor" and user.get("enterprise_id"):
            conditions.append("enterprise_id = :user_enterprise")
            params["user_enterprise"] = user["enterprise_id"]
    return conditions, params


@router.get("/home")
async def dashboard_home(
    fecha_desde: str = Query(None), fecha_hasta: str = Query(None),
    enterprise_id: int = Query(None), fuente: str = Query(None),
    contrato_status: str = Query(None),
    db: AsyncSession = Depends(get_db), user: dict = Depends(get_current_user),
):
    conditions, params = _build_filters(fecha_desde, fecha_hasta, enterprise_id, fuente, user)
    if contrato_status in ("5", "6"):
        conditions.append("status = 15")
        params["contrato_status"] = contrato_status
    where = "WHERE " + " AND ".join(conditions) if conditions else ""

    sql = f"""
        SELECT COUNT(*) FILTER (WHERE status != 30) as leads_nuevos,
               COUNT(*) FILTER (WHERE status IN (5, 10, 15)) as gestionados,
               COUNT(*) FILTER (WHERE (classification_flags->>'es_venta')::int = 1) as ventas
        FROM crm.leads_unificados {where}"""

    current = await db.execute(text(sql), params)
    row = dict(current.fetchone()._mapping)
    leads = row["leads_nuevos"]; ventas = row["ventas"]

    # Previous period: shift dates back by period duration
    prev_leads = leads; prev_gestionados = row["gestionados"]; prev_ventas = ventas
    if fecha_desde and fecha_hasta:
        d1 = datetime.strptime(fecha_desde, "%Y-%m-%d")
        d2 = datetime.strptime(fecha_hasta, "%Y-%m-%d")
        duration = (d2 - d1).days + 1
        prev_desde = (d1 - timedelta(days=duration)).date()
        prev_hasta = (d2 - timedelta(days=duration)).date()
        prev_params = {"fecha_desde": prev_desde, "fecha_hasta": prev_hasta}
        for k, v in params.items():
            if k not in ("fecha_desde", "fecha_hasta"):
                prev_params[k] = v
        prev = await db.execute(text(sql), prev_params)
        prev_row = dict(prev.fetchone()._mapping)
        prev_leads = prev_row["leads_nuevos"]
        prev_gestionados = prev_row["gestionados"]
        prev_ventas = prev_row["ventas"]

    conv = round(ventas/leads*100, 1) if leads > 0 else 0
    conv_prev = round(prev_ventas/prev_leads*100, 1) if prev_leads > 0 else 0

    return {
        "leads_nuevos": leads, "leads_nuevos_prev": prev_leads,
        "gestionados": row["gestionados"], "gestionados_prev": prev_gestionados,
        "ventas": ventas, "ventas_prev": prev_ventas,
        "conversion": conv, "conversion_prev": conv_prev,
    }


@router.get("/vendedores")
async def dashboard_vendedores(
    fecha_desde: str = Query(None), fecha_hasta: str = Query(None),
    enterprise_id: int = Query(None), fuente: str = Query(None),
    contrato_status: str = Query(None),
    db: AsyncSession = Depends(get_db), user: dict = Depends(get_current_user),
):
    conditions, params = _build_filters(fecha_desde, fecha_hasta, enterprise_id, fuente, user)
    conditions.append("seller_id IS NOT NULL")
    where = "WHERE " + " AND ".join(conditions)

    result = await db.execute(text(f"""
        SELECT seller_id, MAX(fullname) as fullname, COUNT(*) as leads,
               COUNT(*) FILTER (WHERE status IN (5, 10, 15)) as gestionados,
               COUNT(*) FILTER (WHERE (classification_flags->>'es_venta')::int = 1) as ventas,
               CASE WHEN COUNT(*) > 0 THEN ROUND(COUNT(*) FILTER (WHERE (classification_flags->>'es_venta')::int = 1)::numeric/COUNT(*)*100, 1) ELSE 0 END as conversion,
               COUNT(*) FILTER (WHERE (classification_flags->>'tipo_cartera') = 'Caliente') as cartera_caliente,
               COUNT(*) FILTER (WHERE (classification_flags->>'tipo_cartera') = 'Fria') as cartera_fria
        FROM crm.leads_unificados {where}
        GROUP BY seller_id ORDER BY ventas DESC LIMIT 50"""), params)
    return [dict(row._mapping) for row in result.fetchall()]


@router.get("/funnel")
async def dashboard_funnel(
    fecha_desde: str = Query(None), fecha_hasta: str = Query(None),
    enterprise_id: int = Query(None), fuente: str = Query(None),
    db: AsyncSession = Depends(get_db), user: dict = Depends(get_current_user),
):
    """Funnel secuencial: cada lead en UNA sola etapa (la mas avanzada)."""
    conditions, params = _build_filters(fecha_desde, fecha_hasta, enterprise_id, fuente, user)
    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""

    # Sequential funnel: each lead classified into exactly ONE stage
    result = await db.execute(text(f"""
        SELECT
            COUNT(*) FILTER (WHERE etapa = 'Nuevo') as nuevos,
            COUNT(*) FILTER (WHERE etapa = 'Contactado') as contactados,
            COUNT(*) FILTER (WHERE etapa = 'Gestionado') as gestionados,
            COUNT(*) FILTER (WHERE etapa = 'Cerrador') as cerrador,
            COUNT(*) FILTER (WHERE etapa = 'Vendido') as vendidos
        FROM (
            SELECT
                CASE
                    WHEN (classification_flags->>'es_venta')::int = 1 THEN 'Vendido'
                    WHEN closer_id IS NOT NULL THEN 'Cerrador'
                    WHEN status IN (10, 15) THEN 'Gestionado'
                    WHEN status IN (5, 6, 12) THEN 'Contactado'
                    WHEN status NOT IN (30) THEN 'Nuevo'
                    ELSE 'Descartado'
                END as etapa
            FROM crm.leads_unificados
            {where}
        ) sub
    """), params)

    row = dict(result.fetchone()._mapping)
    total = sum(row.values()) or 1

    etapas = [
        ("Nuevo", "Nuevos", row["nuevos"]),
        ("Contactado", "Contactados", row["contactados"]),
        ("Gestionado", "Gestionados", row["gestionados"]),
        ("Cerrador", "En cerrador", row["cerrador"]),
        ("Vendido", "Vendidos", row["vendidos"]),
    ]
    return {"etapas": [
        {"nombre": label, "valor": v, "pct": round(v / total * 100, 1)} for _, label, v in etapas
    ]}


@router.get("/supervisores")
async def dashboard_supervisores(
    fecha_desde: str = Query(None), fecha_hasta: str = Query(None),
    enterprise_id: int = Query(None), fuente: str = Query(None),
    db: AsyncSession = Depends(get_db), user: dict = Depends(get_current_user),
):
    """Supervisor ranking + drill-down: grouped by UN. Names from cache."""
    conditions, params = _build_filters(fecha_desde, fecha_hasta, enterprise_id, fuente, user)
    conditions.append("seller_id IS NOT NULL")
    where = "WHERE " + " AND ".join(conditions)

    result = await db.execute(text(f"""
        SELECT enterprise_id, COUNT(*) as leads,
               COUNT(*) FILTER (WHERE status IN (5, 10, 15)) as gestionados,
               COUNT(*) FILTER (WHERE (classification_flags->>'es_venta')::int = 1) as ventas,
               CASE WHEN COUNT(*) > 0 THEN ROUND(COUNT(*) FILTER (WHERE (classification_flags->>'es_venta')::int = 1)::numeric/COUNT(*)*100, 1) ELSE 0 END as conversion,
               COUNT(DISTINCT seller_id) as vendedores
        FROM crm.leads_unificados {where}
        GROUP BY enterprise_id ORDER BY ventas DESC"""), params)

    return [{
        "enterprise_id": r["enterprise_id"],
        "un_nombre": _un_names.get(r["enterprise_id"], f"UN {r['enterprise_id']}"),
        "leads": r["leads"], "gestionados": r["gestionados"],
        "ventas": r["ventas"], "conversion": r["conversion"],
        "vendedores": r["vendedores"],
    } for r in [dict(row._mapping) for row in result.fetchall()]]


@router.get("/campanas")
async def dashboard_campanas(
    fecha_desde: str = Query(None), fecha_hasta: str = Query(None),
    enterprise_id: int = Query(None), fuente: str = Query(None),
    db: AsyncSession = Depends(get_db), user: dict = Depends(get_current_user),
):
    """Top campaigns with REAL names from EPEM MySQL."""
    conditions, params = _build_filters(fecha_desde, fecha_hasta, enterprise_id, fuente, user)
    conditions.append("campaign_id IS NOT NULL")
    where = "WHERE " + " AND ".join(conditions)

    result = await db.execute(text(f"""
        SELECT campaign_id, COUNT(*) as leads,
               COUNT(*) FILTER (WHERE (classification_flags->>'es_venta')::int = 1) as ventas,
               CASE WHEN COUNT(*) > 0 THEN ROUND(COUNT(*) FILTER (WHERE (classification_flags->>'es_venta')::int = 1)::numeric/COUNT(*)*100, 1) ELSE 0 END as conversion
        FROM crm.leads_unificados {where}
        GROUP BY campaign_id ORDER BY leads DESC LIMIT 20"""), params)

    # Enrich with real names from EPEM
    names = _load_campaign_names()
    return [{
        "campaign_id": r["campaign_id"],
        "campaign_name": names.get(r["campaign_id"], f"Campana #{r['campaign_id']}"),
        "leads": r["leads"], "ventas": r["ventas"], "conversion": r["conversion"],
    } for r in [dict(row._mapping) for row in result.fetchall()]]


@router.get("/alertas")
async def dashboard_alertas(
    db: AsyncSession = Depends(get_db), user: dict = Depends(get_current_user),
):
    conditions_lead, params_lead = _build_filters(None, None, None, None, user)
    where = ("WHERE " + " AND ".join(conditions_lead)) if conditions_lead else ""
    prefix = "AND" if where else "WHERE"

    leads_24h = await db.execute(text(f"""
        SELECT COUNT(*) as total FROM crm.leads_unificados {where}
        {prefix} status NOT IN (5,6,10,12,15,30) AND first_seen_at < NOW() - INTERVAL '24 hours'"""), params_lead)
    count = leads_24h.fetchone()[0]
    return {
        "leads_sin_contactar_24h": count, "alerta": count > 0,
        "mensaje": f"Hay {count} leads sin contacto en mas de 24 horas" if count > 0 else "Todos los leads estan al dia",
    }


@router.get("/cruces-epem")
async def dashboard_cruces_epem(
    fecha_desde: str = Query(None), fecha_hasta: str = Query(None),
    enterprise_id: int = Query(None),
    db: AsyncSession = Depends(get_db), user: dict = Depends(get_current_user),
):
    """Cross EPEM: DW sales vs real vouchers from EPEM MySQL."""
    import pymysql

    # 1. Get DW sales: leads with es_venta=1 in period
    dw_conditions = ["(classification_flags->>'es_venta')::int = 1"]
    dw_params = {}
    if fecha_desde:
        dw_conditions.append("first_seen_at >= :fecha_desde")
        dw_params["fecha_desde"] = fecha_desde
    if fecha_hasta:
        dw_conditions.append("first_seen_at <= :fecha_hasta + interval '1 day'")
        dw_params["fecha_hasta"] = fecha_hasta
    if enterprise_id:
        dw_conditions.append("enterprise_id = :enterprise_id")
        dw_params["enterprise_id"] = enterprise_id
    dw_where = "WHERE " + " AND ".join(dw_conditions)

    dw_result = await db.execute(text(f"""
        SELECT COUNT(*) as total_ventas,
               COUNT(DISTINCT contract_id) as contratos,
               COUNT(DISTINCT seller_id) as vendedores
        FROM crm.leads_unificados {dw_where}"""), dw_params)
    dw = dict(dw_result.fetchone()._mapping)

    # 2. Get real vouchers from EPEM MySQL for the same period
    vouchers_activos = 0
    vouchers_monto = 0
    vouchers_count = 0

    try:
        conn = pymysql.connect(
            host=settings.EPEM_DB_HOST, port=settings.EPEM_DB_PORT,
            user=settings.EPEM_DB_USER, password=settings.EPEM_DB_PASSWORD,
            database=settings.EPEM_DB_NAME, charset="utf8mb4", connect_timeout=10
        )
        cur = conn.cursor(pymysql.cursors.DictCursor)

        # Build date filter for EPEM vouchers
        epem_where = []
        epem_params = []
        if fecha_desde:
            epem_where.append("v.from_date >= %s")
            epem_params.append(fecha_desde)
        if fecha_hasta:
            epem_where.append("v.from_date <= %s")
            epem_params.append(fecha_hasta)
        if enterprise_id:
            epem_where.append("v.enterprise_id = %s")
            epem_params.append(enterprise_id)

        epem_where_clause = " AND ".join(epem_where) if epem_where else "1=1"
        cur.execute(f"""
            SELECT COUNT(DISTINCT v.id) as total_vouchers,
                   COUNT(DISTINCT v.contract_id) as contratos,
                   COALESCE(SUM(v.total), 0) as monto_total
            FROM vouchers v
            WHERE v.status = 5 AND v.deleted_at IS NULL
              AND {epem_where_clause}
        """, epem_params)
        epem = cur.fetchone()
        vouchers_activos = epem["total_vouchers"]
        vouchers_contratos = epem["contratos"]
        vouchers_monto = int(epem["monto_total"])

        # Count by enterprise for UN breakdown
        cur.execute(f"""
            SELECT v.enterprise_id,
                   COUNT(DISTINCT v.id) as vouchers,
                   COALESCE(SUM(v.total), 0) as monto
            FROM vouchers v
            WHERE v.status = 5 AND v.deleted_at IS NULL
              AND {epem_where_clause}
            GROUP BY v.enterprise_id
            ORDER BY vouchers DESC
        """, epem_params)
        epem_by_un = cur.fetchall()

        cur.close(); conn.close()
    except Exception as e:
        vouchers_monto = -1
        epem_by_un = []
        epem_error = str(e)

    # 3. Cross-match: DW contract_ids that have vouchers in EPEM
    # (simplified: count contracts that appear in both)
    match_rate = 0
    if dw["contratos"] > 0 and vouchers_count > 0:
        match_rate = round(min(vouchers_count, dw["contratos"]) / dw["contratos"] * 100, 1)

    return {
        "dw_ventas": {
            "total": dw["total_ventas"],
            "contratos_unicos": dw["contratos"],
            "vendedores": dw["vendedores"],
        },
        "epem_vouchers": {
            "activos": vouchers_activos,
            "monto_total": vouchers_monto,
            "monto_promedio": vouchers_monto // vouchers_activos if vouchers_activos > 0 else 0,
        },
        "por_unidad": [{
            "enterprise_id": u["enterprise_id"],
            "un_nombre": _un_names.get(u["enterprise_id"], f"UN {u['enterprise_id']}"),
            "vouchers": u["vouchers"],
            "monto": int(u["monto"]),
        } for u in epem_by_un],
        "error": epem_error if 'epem_error' in dir() else None,
    }
