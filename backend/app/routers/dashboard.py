"""
CRM Unificado EPEM — Dashboard Router (Enhanced)
Funnel secuencial + Campanas con nombres + Supervisores drill-down + Filtros
"""
from datetime import date, datetime, timedelta
from fastapi import APIRouter, Depends, Query, HTTPException
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
_seller_names: dict = {}  # seller_id → "First Last"
_supervisor_names: dict = {}  # supervisor_id → "First Last"
_seller_supervisor_map: dict = {}  # seller_id → supervisor_id


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


def _load_seller_names():
    """Load seller names from EPEM users table into a cache dict."""
    global _seller_names
    if _seller_names:
        return _seller_names
    try:
        import pymysql
        conn = pymysql.connect(
            host=settings.EPEM_DB_HOST, port=settings.EPEM_DB_PORT,
            user=settings.EPEM_DB_USER, password=settings.EPEM_DB_PASSWORD,
            database=settings.EPEM_DB_NAME, charset="utf8mb4", connect_timeout=10
        )
        cur = conn.cursor(pymysql.cursors.DictCursor)
        cur.execute("SELECT id, CONCAT(first_name, ' ', last_name) as fullname FROM users WHERE seller = 1")
        _seller_names = {row["id"]: row["fullname"] for row in cur.fetchall()}
        cur.close(); conn.close()
        print(f"[SELLERS] Loaded {len(_seller_names)} seller names from EPEM users")
    except Exception as e:
        print(f"[SELLERS] Failed to load: {e}")
        _seller_names = {-1: f"Error: {e}"}
    return _seller_names


def _get_seller_name(seller_id: int) -> str:
    """Get real seller name from cache, fallback to ID if not found."""
    _load_seller_names()
    name = _seller_names.get(seller_id)
    if name:
        return name
    if seller_id == 1:
        return "SISTEMA EPEM"
    return f"Vendedor #{seller_id}"


def _load_supervisor_data():
    """Load supervisor names and seller→supervisor mapping from EPEM users."""
    global _supervisor_names, _seller_supervisor_map
    try:
        import pymysql
        conn = pymysql.connect(
            host=settings.EPEM_DB_HOST, port=settings.EPEM_DB_PORT,
            user=settings.EPEM_DB_USER, password=settings.EPEM_DB_PASSWORD,
            database=settings.EPEM_DB_NAME, charset="utf8mb4", connect_timeout=10
        )
        cur = conn.cursor(pymysql.cursors.DictCursor)
        cur.execute("SELECT id as seller_id, seller_supervisor_id FROM users WHERE seller = 1 AND seller_supervisor_id IS NOT NULL")
        _seller_supervisor_map = {int(row["seller_id"]): int(row["seller_supervisor_id"]) for row in cur.fetchall()}
        sup_ids = set(_seller_supervisor_map.values())
        if sup_ids:
            placeholders = ",".join(str(sid) for sid in sup_ids)
            cur.execute(f"SELECT id, CONCAT(first_name, ' ', last_name) as fullname FROM users WHERE id IN ({placeholders})")
            _supervisor_names = {int(row["id"]): row["fullname"] for row in cur.fetchall()}
        cur.close(); conn.close()
        print(f"[SUPERVISORS] Loaded {len(_supervisor_names)} supervisors, {len(_seller_supervisor_map)} seller->supervisor mappings")
    except Exception as e:
        print(f"[SUPERVISORS] Failed to load: {e}")
        import traceback; traceback.print_exc()
        _supervisor_names = {}
        _seller_supervisor_map = {}


def _build_filters(fecha_desde, fecha_hasta, enterprise_id, fuente, user=None, status=None, campaign_id=None):
    conditions = []
    params = {}
    if fecha_desde:
        conditions.append("first_seen_at >= :fecha_desde")
        params["fecha_desde"] = datetime.strptime(fecha_desde, "%Y-%m-%d").date()
    if fecha_hasta:
        conditions.append("first_seen_at <= :fecha_hasta")
        params["fecha_hasta"] = (datetime.strptime(fecha_hasta, "%Y-%m-%d") + timedelta(days=1)).date()
    if enterprise_id:
        conditions.append("enterprise_id = :enterprise_id")
        params["enterprise_id"] = enterprise_id
    if fuente:
        # Filtro robusto: unifica ThinkChat->Venta a ThinkChat (single source of truth)
        conditions.append("SPLIT_PART(classification_flags->>'origen_lead', '->', 1) = :fuente")
        params["fuente"] = fuente
    if status:
        conditions.append("status = :status")
        params["status"] = status
    if campaign_id:
        conditions.append("campaign_id = :campaign_id")
        params["campaign_id"] = campaign_id
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
               COUNT(DISTINCT contract_id) FILTER (WHERE (classification_flags->>'es_venta')::int = 1 AND contract_id IS NOT NULL) as ventas
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
        "tasa_contacto": round(row["gestionados"]/leads*100,1) if leads>0 else 0,
        "tasa_contacto_prev": round(prev_gestionados/prev_leads*100,1) if prev_leads>0 else 0,
    }


@router.get("/home-extended")
async def dashboard_home_extended(
    fecha_desde: str = Query(None), fecha_hasta: str = Query(None),
    enterprise_id: int = Query(None), fuente: str = Query(None),
    db: AsyncSession = Depends(get_db), user: dict = Depends(get_current_user),
):
    conditions, params = _build_filters(fecha_desde, fecha_hasta, enterprise_id, fuente, user)
    where = "WHERE " + " AND ".join(conditions) if conditions else ""

    # KPIs by source
    # NOTA: 'ThinkChat->Venta' se unifica a 'ThinkChat' (la fuente es ThinkChat, el flag es_venta=1
    # marca si es venta o no). Esto evita duplicar la fila en el dashboard.
    # IMPORTANTE: usar COUNT(DISTINCT contract_id) para ventas porque un mismo contrato puede
    # tener multiples leads (caso real: 2 sales_opportunities apuntando al mismo contract_id).
    by_source = await db.execute(text(f"""
        SELECT SPLIT_PART(classification_flags->>'origen_lead', '->', 1) as fuente,
               COUNT(*) as leads,
               COUNT(*) FILTER (WHERE status IN (5,10,15)) as gestionados,
               COUNT(DISTINCT contract_id) FILTER (WHERE (classification_flags->>'es_venta')::int = 1 AND contract_id IS NOT NULL) as ventas
        FROM crm.leads_unificados {where}
        GROUP BY fuente ORDER BY leads DESC"""), params)
    sources = [dict(r._mapping) for r in by_source.fetchall()]

    # KPIs by UN
    by_un = await db.execute(text(f"""
        SELECT enterprise_id, COUNT(*) as leads,
               COUNT(*) FILTER (WHERE status IN (5,10,15)) as gestionados,
               COUNT(*) FILTER (WHERE (classification_flags->>'es_venta')::int = 1) as ventas
        FROM crm.leads_unificados {where}
        GROUP BY enterprise_id ORDER BY leads DESC"""), params)
    uns = [dict(r._mapping) for r in by_un.fetchall()]

    # Pipeline velocity: avg hours from first_seen to first status change
    vel_prefix = "AND" if conditions else "WHERE"
    velocity = await db.execute(text(f"""
        SELECT AVG(EXTRACT(EPOCH FROM (last_updated_at - first_seen_at))/3600)::int as avg_hours_to_contact,
               COUNT(*) FILTER (WHERE last_updated_at > first_seen_at) as contacted_count
        FROM crm.leads_unificados {where}
        {vel_prefix} status IN (5,6,10,12,15)"""), params)
    vel = dict(velocity.fetchone()._mapping)

    # Lost leads
    lost_prefix = "AND" if conditions else "WHERE"
    lost = await db.execute(text(f"""
        SELECT COUNT(*) as perdidos FROM crm.leads_unificados {where}
        {lost_prefix} status = 30"""), params)
    lost_count = lost.fetchone()[0]

    # Today's leads (last 24h from now)
    yesterday_utc = datetime.utcnow() - timedelta(hours=24)
    today_sql = f"""
        SELECT COUNT(*) as hoy FROM crm.leads_unificados {where}
        {'AND' if conditions else 'WHERE'} first_seen_at >= :today_cutoff"""
    today_params = {**params, "today_cutoff": yesterday_utc}
    today = await db.execute(text(today_sql), today_params)
    today_count = today.fetchone()[0]

    return {
        "por_fuente": [{"fuente": r["fuente"] or "N/A", "leads": r["leads"], "gestionados": r["gestionados"], "ventas": r["ventas"]} for r in sources],
        "por_un": [{"enterprise_id": r["enterprise_id"], "leads": r["leads"], "ventas": r["ventas"]} for r in uns],
        "pipeline_velocity": {"avg_hours": vel["avg_hours_to_contact"] or 0, "contacted": vel["contacted_count"]},
        "leads_perdidos": lost_count,
        "leads_hoy": today_count,
    }


@router.get("/timeline")
async def dashboard_timeline(
    days: int = Query(7), enterprise_id: int = Query(None),
    fuente: str = Query(None),
    db: AsyncSession = Depends(get_db), user: dict = Depends(get_current_user),
):
    conds = []
    p = {}
    if enterprise_id:
        conds.append("enterprise_id = :eid")
        p["eid"] = enterprise_id
    if fuente:
        conds.append("SPLIT_PART(classification_flags->>'origen_lead', '->', 1) = :fuente")
        p["fuente"] = fuente
    w = "WHERE " + " AND ".join(conds) if conds else ""
    prefix = "AND" if conds else "WHERE"
    cutoff = date.today() - timedelta(days=days)
    result = await db.execute(text(f"""
        SELECT DATE(first_seen_at) as dia,
               COUNT(*) as leads,
               COUNT(*) FILTER (WHERE status IN (5,10,15)) as gestionados,
               COUNT(DISTINCT contract_id) FILTER (WHERE (classification_flags->>'es_venta')::int = 1 AND contract_id IS NOT NULL) as ventas
        FROM crm.leads_unificados {w}
        {prefix} first_seen_at >= :cutoff
        GROUP BY dia ORDER BY dia"""), {**p, "cutoff": cutoff})
    return [dict(r._mapping) for r in result.fetchall()]


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
        SELECT seller_id, COUNT(*) as leads,
               COUNT(*) FILTER (WHERE status IN (5, 10, 15)) as gestionados,
               COUNT(DISTINCT contract_id) FILTER (WHERE (classification_flags->>'es_venta')::int = 1 AND contract_id IS NOT NULL) as ventas,
               CASE WHEN COUNT(*) > 0 THEN ROUND(COUNT(DISTINCT contract_id) FILTER (WHERE (classification_flags->>'es_venta')::int = 1 AND contract_id IS NOT NULL)::numeric/COUNT(*)*100, 1) ELSE 0 END as conversion,
               COUNT(*) FILTER (WHERE (classification_flags->>'tipo_cartera') = 'Caliente') as cartera_caliente,
               COUNT(*) FILTER (WHERE (classification_flags->>'tipo_cartera') = 'Fria') as cartera_fria
        FROM crm.leads_unificados {where}
        GROUP BY seller_id ORDER BY ventas DESC"""), params)
    rows = [dict(row._mapping) for row in result.fetchall()]
    # Resolve real seller names from EPEM users table
    _load_seller_names()
    for r in rows:
        r["fullname"] = _get_seller_name(r["seller_id"])

    # Previous period comparativa
    if fecha_desde and fecha_hasta and conditions:
        d1 = datetime.strptime(fecha_desde, "%Y-%m-%d")
        d2 = datetime.strptime(fecha_hasta, "%Y-%m-%d")
        duration = (d2 - d1).days + 1
        prev_desde = (d1 - timedelta(days=duration)).date()
        prev_hasta = (d2 - timedelta(days=duration)).date()
        pparams = {k: v for k, v in params.items() if k not in ("fecha_desde", "fecha_hasta")}
        pparams["fecha_desde"] = prev_desde
        pparams["fecha_hasta"] = prev_hasta
        try:
            prev_res = await db.execute(text(f"""
                SELECT seller_id, COUNT(*) as leads,
                       COUNT(*) FILTER (WHERE status IN (5,10,15)) as gestionados,
                       COUNT(DISTINCT contract_id) FILTER (WHERE (classification_flags->>'es_venta')::int = 1 AND contract_id IS NOT NULL) as ventas
                FROM crm.leads_unificados {where}
                GROUP BY seller_id"""), pparams)
            prev_map = {r["seller_id"]: dict(r) for r in prev_res.fetchall()}
            for r in rows:
                p = prev_map.get(r["seller_id"], {})
                r["leads_prev"] = p.get("leads", 0)
                r["gestionados_prev"] = p.get("gestionados", 0)
                r["ventas_prev"] = p.get("ventas", 0)
        except Exception:
            for r in rows:
                r["leads_prev"] = 0
                r["gestionados_prev"] = 0
                r["ventas_prev"] = 0
    else:
        for r in rows:
            r["leads_prev"] = 0
            r["gestionados_prev"] = 0
            r["ventas_prev"] = 0

    return rows


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
    """Supervisores reales: métricas de su equipo de vendedores. Drilldown: sellers del equipo."""
    conditions, params = _build_filters(fecha_desde, fecha_hasta, enterprise_id, fuente, user)
    conditions.append("seller_id IS NOT NULL")
    where = "WHERE " + " AND ".join(conditions)

    # Get per-seller stats from CRM
    result = await db.execute(text(f"""
        SELECT seller_id, COUNT(*) as leads,
               COUNT(*) FILTER (WHERE status IN (5, 10, 15)) as gestionados,
               COUNT(DISTINCT contract_id) FILTER (WHERE (classification_flags->>'es_venta')::int = 1 AND contract_id IS NOT NULL) as ventas,
               CASE WHEN COUNT(*) > 0 THEN ROUND(COUNT(DISTINCT contract_id) FILTER (WHERE (classification_flags->>'es_venta')::int = 1 AND contract_id IS NOT NULL)::numeric/COUNT(*)*100, 1) ELSE 0 END as conversion
        FROM crm.leads_unificados {where}
        GROUP BY seller_id ORDER BY ventas DESC"""), params)
    seller_rows = [dict(row._mapping) for row in result.fetchall()]

    # Load supervisor mapping from EPEM
    _load_supervisor_data()
    _load_seller_names()

    # Group sellers by supervisor
    supervisor_data: dict = {}  # supervisor_id → {leads, gestionados, ventas, sellers: [...]}
    unassigned = {"leads": 0, "gestionados": 0, "ventas": 0, "sellers": []}

    for s in seller_rows:
        sid = s["seller_id"]
        sup_id = _seller_supervisor_map.get(sid)
        s["fullname"] = _get_seller_name(sid)
        if sup_id and sup_id in _supervisor_names:
            if sup_id not in supervisor_data:
                supervisor_data[sup_id] = {"leads": 0, "gestionados": 0, "ventas": 0, "sellers": []}
            supervisor_data[sup_id]["leads"] += s["leads"]
            supervisor_data[sup_id]["gestionados"] += s["gestionados"]
            supervisor_data[sup_id]["ventas"] += s["ventas"]
            supervisor_data[sup_id]["sellers"].append(s)
        else:
            unassigned["leads"] += s["leads"]
            unassigned["gestionados"] += s["gestionados"]
            unassigned["ventas"] += s["ventas"]
            unassigned["sellers"].append(s)

    # Build response
    rows = []
    for sup_id, data in sorted(supervisor_data.items(), key=lambda x: -x[1]["ventas"]):
        total_leads = data["leads"]
        rows.append({
            "supervisor_id": sup_id,
            "supervisor_nombre": _supervisor_names[sup_id],
            "leads": total_leads,
            "gestionados": data["gestionados"],
            "ventas": data["ventas"],
            "conversion": round(data["ventas"] / total_leads * 100, 1) if total_leads > 0 else 0,
            "vendedores": len(data["sellers"]),
            "_sellers": data["sellers"],  # for drilldown
        })

    # Add unassigned as last row
    if unassigned["sellers"]:
        total_un = unassigned["leads"]
        rows.append({
            "supervisor_id": 0,
            "supervisor_nombre": "Sin supervisor asignado",
            "leads": total_un,
            "gestionados": unassigned["gestionados"],
            "ventas": unassigned["ventas"],
            "conversion": round(unassigned["ventas"] / total_un * 100, 1) if total_un > 0 else 0,
            "vendedores": len(unassigned["sellers"]),
            "_sellers": unassigned["sellers"],
        })

    return rows


@router.get("/funnel-asignacion")
async def dashboard_funnel_asignacion(
    fecha_desde: str = Query(None), fecha_hasta: str = Query(None),
    enterprise_id: int = Query(None), fuente: str = Query(None),
    db: AsyncSession = Depends(get_db), user: dict = Depends(get_current_user),
):
    """Funnel de asignación: leads entrantes → asignados vs huérfanos (seller_id=1 o NULL).
    Breakdown por UN, fuente, y supervisor. Tiempo hasta asignación."""
    conditions, params = _build_filters(fecha_desde, fecha_hasta, enterprise_id, fuente, user)
    where = "WHERE " + " AND ".join(conditions) if conditions else ""
    prefix = "AND" if conditions else "WHERE"

    # ── 1. GLOBAL: asignados vs huérfanos ──
    global_stats = await db.execute(text(f"""
        SELECT
          COUNT(*) as total_leads,
          COUNT(*) FILTER (WHERE seller_id IS NOT NULL AND seller_id != 1) as asignados,
          COUNT(*) FILTER (WHERE seller_id = 1) as sistema_epem,
          COUNT(*) FILTER (WHERE seller_id IS NULL) as sin_seller,
          COUNT(*) FILTER (WHERE status IN (5,10,15)) as gestionados,
          COUNT(DISTINCT contract_id) FILTER (WHERE (classification_flags->>'es_venta')::int = 1 AND contract_id IS NOT NULL) as ventas
        FROM crm.leads_unificados {where}"""), params)
    g = dict(global_stats.fetchone()._mapping)
    total = g["total_leads"] or 1
    global_data = {
        "total_leads": g["total_leads"],
        "asignados": g["asignados"],
        "asignados_pct": round(g["asignados"] / total * 100, 1),
        "sistema_epem": g["sistema_epem"],
        "sistema_epem_pct": round(g["sistema_epem"] / total * 100, 1),
        "sin_seller": g["sin_seller"],
        "sin_seller_pct": round(g["sin_seller"] / total * 100, 1),
        "huerfanos_total": g["sistema_epem"] + (g["sin_seller"] or 0),
        "huerfanos_pct": round((g["sistema_epem"] + (g["sin_seller"] or 0)) / total * 100, 1),
        "gestionados": g["gestionados"],
        "ventas": g["ventas"],
    }

    # ── 2. POR UN ──
    by_un = await db.execute(text(f"""
        SELECT enterprise_id,
               COUNT(*) as total_leads,
               COUNT(*) FILTER (WHERE seller_id IS NOT NULL AND seller_id != 1) as asignados,
               COUNT(*) FILTER (WHERE seller_id = 1) as sistema_epem,
               COUNT(*) FILTER (WHERE seller_id IS NULL) as sin_seller,
               COUNT(*) FILTER (WHERE status IN (5,10,15)) as gestionados,
               COUNT(DISTINCT contract_id) FILTER (WHERE (classification_flags->>'es_venta')::int = 1 AND contract_id IS NOT NULL) as ventas
        FROM crm.leads_unificados {where}
        GROUP BY enterprise_id ORDER BY total_leads DESC"""), params)
    por_un = []
    for r in by_un.mappings().all():
        d = dict(r)
        t = d["total_leads"] or 1
        por_un.append({
            "enterprise_id": d["enterprise_id"],
            "un_nombre": _un_names.get(d["enterprise_id"], f"UN {d['enterprise_id']}"),
            "total_leads": d["total_leads"],
            "asignados": d["asignados"],
            "asignados_pct": round(d["asignados"] / t * 100, 1),
            "huerfanos": (d["sistema_epem"] or 0) + (d["sin_seller"] or 0),
            "huerfanos_pct": round(((d["sistema_epem"] or 0) + (d["sin_seller"] or 0)) / t * 100, 1),
            "gestionados": d["gestionados"],
            "ventas": d["ventas"],
        })

    # ── 3. POR FUENTE ──
    by_fuente = await db.execute(text(f"""
        SELECT SPLIT_PART(COALESCE(classification_flags->>'origen_lead', 'Manual'), '->', 1) as fuente,
               COUNT(*) as total_leads,
               COUNT(*) FILTER (WHERE seller_id IS NOT NULL AND seller_id != 1) as asignados,
               COUNT(*) FILTER (WHERE seller_id = 1) as sistema_epem,
               COUNT(*) FILTER (WHERE seller_id IS NULL) as sin_seller,
               COUNT(*) FILTER (WHERE status IN (5,10,15)) as gestionados,
               COUNT(DISTINCT contract_id) FILTER (WHERE (classification_flags->>'es_venta')::int = 1 AND contract_id IS NOT NULL) as ventas
        FROM crm.leads_unificados {where}
        GROUP BY fuente ORDER BY total_leads DESC"""), params)
    por_fuente = []
    for r in by_fuente.mappings().all():
        d = dict(r)
        t = d["total_leads"] or 1
        por_fuente.append({
            "fuente": d["fuente"],
            "total_leads": d["total_leads"],
            "asignados": d["asignados"],
            "asignados_pct": round(d["asignados"] / t * 100, 1),
            "huerfanos": (d["sistema_epem"] or 0) + (d["sin_seller"] or 0),
            "huerfanos_pct": round(((d["sistema_epem"] or 0) + (d["sin_seller"] or 0)) / t * 100, 1),
            "gestionados": d["gestionados"],
            "ventas": d["ventas"],
        })

    # ── 4. POR SUPERVISOR ── cuántos leads recibe el equipo de cada supervisor
    _load_supervisor_data()
    _load_seller_names()
    seller_stats = await db.execute(text(f"""
        SELECT seller_id, COUNT(*) as leads,
               COUNT(*) FILTER (WHERE status IN (5,10,15)) as gestionados,
               COUNT(DISTINCT contract_id) FILTER (WHERE (classification_flags->>'es_venta')::int = 1 AND contract_id IS NOT NULL) as ventas
        FROM crm.leads_unificados {where}
        {prefix} seller_id IS NOT NULL AND seller_id != 1
        GROUP BY seller_id"""), params)
    sup_leads: dict = {}
    for r in seller_stats.mappings().all():
        d = dict(r)
        sid = d["seller_id"]
        sup_id = _seller_supervisor_map.get(sid)
        if sup_id and sup_id in _supervisor_names:
            if sup_id not in sup_leads:
                sup_leads[sup_id] = {"leads": 0, "gestionados": 0, "ventas": 0, "sellers": 0}
            sup_leads[sup_id]["leads"] += d["leads"]
            sup_leads[sup_id]["gestionados"] += d["gestionados"]
            sup_leads[sup_id]["ventas"] += d["ventas"]
            sup_leads[sup_id]["sellers"] += 1

    por_supervisor = []
    for sup_id, data in sorted(sup_leads.items(), key=lambda x: -x[1]["leads"]):
        por_supervisor.append({
            "supervisor_id": sup_id,
            "supervisor_nombre": _supervisor_names[sup_id],
            "leads_asignados": data["leads"],
            "gestionados": data["gestionados"],
            "ventas": data["ventas"],
            "vendedores": data["sellers"],
            "tasa_gestion": round(data["gestionados"] / data["leads"] * 100, 1) if data["leads"] > 0 else 0,
        })

    # ── 5. TREND MENSUAL DE ASIGNACIÓN ──
    trend = await db.execute(text(f"""
        SELECT DATE_TRUNC('month', first_seen_at) as mes,
               COUNT(*) as total_leads,
               COUNT(*) FILTER (WHERE seller_id IS NOT NULL AND seller_id != 1) as asignados,
               COUNT(*) FILTER (WHERE seller_id = 1 OR seller_id IS NULL) as huerfanos
        FROM crm.leads_unificados
        WHERE first_seen_at >= DATE_TRUNC('month', CURRENT_DATE) - INTERVAL '12 months'
        GROUP BY mes ORDER BY mes"""))
    trend_mensual = []
    for r in trend.mappings().all():
        d = dict(r)
        t = d["total_leads"] or 1
        trend_mensual.append({
            "mes_str": str(d["mes"])[:7],
            "total_leads": d["total_leads"],
            "asignados": d["asignados"],
            "asignados_pct": round(d["asignados"] / t * 100, 1),
            "huerfanos": d["huerfanos"],
            "huerfanos_pct": round(d["huerfanos"] / t * 100, 1),
        })

    return {
        "global": global_data,
        "por_un": por_un,
        "por_fuente": por_fuente,
        "por_supervisor": por_supervisor,
        "trend_mensual": trend_mensual,
    }


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
               COUNT(DISTINCT contract_id) FILTER (WHERE (classification_flags->>'es_venta')::int = 1 AND contract_id IS NOT NULL) as ventas,
               CASE WHEN COUNT(*) > 0 THEN ROUND(COUNT(DISTINCT contract_id) FILTER (WHERE (classification_flags->>'es_venta')::int = 1 AND contract_id IS NOT NULL)::numeric/COUNT(*)*100, 1) ELSE 0 END as conversion
        FROM crm.leads_unificados {where}
        GROUP BY campaign_id ORDER BY leads DESC LIMIT 20"""), params)
    rows = [dict(row._mapping) for row in result.fetchall()]

    # Previous period — only if explicit date range
    prev_rows = {}
    if fecha_desde and fecha_hasta and conditions:
        d1 = datetime.strptime(fecha_desde, "%Y-%m-%d")
        d2 = datetime.strptime(fecha_hasta, "%Y-%m-%d")
        duration = (d2 - d1).days + 1
        prev_desde = (d1 - timedelta(days=duration)).date()
        prev_hasta = (d2 - timedelta(days=duration)).date()
        pparams = {k: v for k, v in params.items() if k not in ("fecha_desde", "fecha_hasta")}
        pparams["fecha_desde"] = prev_desde
        pparams["fecha_hasta"] = prev_hasta
        try:
            prev_res = await db.execute(text(f"""
                SELECT campaign_id, COUNT(*) as leads,
                       COUNT(DISTINCT contract_id) FILTER (WHERE (classification_flags->>'es_venta')::int = 1 AND contract_id IS NOT NULL) as ventas
                FROM crm.leads_unificados {where}
                GROUP BY campaign_id"""), pparams)
            prev_rows = {r["campaign_id"]: dict(r) for r in prev_res.fetchall()}
        except Exception:
            prev_rows = {}

    # Enrich with real names from EPEM
    names = _load_campaign_names()
    return [{
        "campaign_id": r["campaign_id"],
        "campaign_name": names.get(r["campaign_id"], f"Campana #{r['campaign_id']}"),
        "leads": r["leads"], "leads_prev": prev_rows.get(r["campaign_id"], {}).get("leads", 0),
        "ventas": r["ventas"], "ventas_prev": prev_rows.get(r["campaign_id"], {}).get("ventas", 0),
        "conversion": r["conversion"],
    } for r in rows]


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


@router.get("/lead")
async def dashboard_lead_search(
    q: str = Query(...),
    fuente: str = Query(None, description="Filtrar por fuente: Botmaker, ThinkChat, Manual"),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """Search lead by phone or name, return timeline data from EPEM + CRM DW."""
    import pymysql

    # 1. Search in CRM DW for the lead
    dw_sql = """
        SELECT id, normalized_phone as phone, fullname, status, enterprise_id, seller_id,
               closer_id, contract_id, first_seen_at,
               classification_flags
        FROM crm.leads_unificados
        WHERE normalized_phone = :phone OR fullname ILIKE :name
    """
    dw_params = {"phone": q.strip(), "name": f"%{q.strip()}%"}
    if fuente:
        # Filtro robusto: unifica ThinkChat->Venta a ThinkChat para que el match funcione
        dw_sql += " AND SPLIT_PART(classification_flags->>'origen_lead', '->', 1) = :fuente"
        dw_params["fuente"] = fuente
    dw_sql += " LIMIT 5"
    dw_result = await db.execute(text(dw_sql), dw_params)
    dw_leads = [dict(row._mapping) for row in dw_result.fetchall()]

    # Enrich DW matches with fuente badge info from classification_flags
    for dw in dw_leads:
        flags = dw.get("classification_flags") or {}
        if isinstance(flags, str):
            import json
            try:
                flags = json.loads(flags)
            except:
                flags = {}
        dw["fuente_origen"] = flags.get("origen_lead") or "Manual"
        dw["es_venta_dw"] = bool(flags.get("es_venta"))

    # 2. Search in EPEM for detailed timeline
    epem_leads = []
    try:
        epem = pymysql.connect(
            host=settings.EPEM_DB_HOST, port=settings.EPEM_DB_PORT,
            user=settings.EPEM_DB_USER, password=settings.EPEM_DB_PASSWORD,
            database=settings.EPEM_DB_NAME, charset="utf8mb4", connect_timeout=10
        )
        cur = epem.cursor(pymysql.cursors.DictCursor)

        # Search by phone (strip prefix)
        phone = q.strip()
        cur.execute("""
            SELECT so.id, so.phone, so.fullname, so.status, so.enterprise_id,
                   so.seller_id, so.closer_id, so.contract_id,
                   so.created_at, so.updated_at, so.closed_at, so.selled_at,
                   so.rejected_at, so.rejected_motive_id, so.deadline,
                   so.city_id, so.ad_id, so.ad_set_id,
                   so.lead, so.observation, so.form_id, so.notificated, so.scheduled,
                   so.closed_in, so.drawer_sale_at, so.deadline,
                   u.first_name, u.last_name,
                   c.first_name as closer_first, c.last_name as closer_last
            FROM sales_opportunities so
            LEFT JOIN users u ON so.seller_id = u.id
            LEFT JOIN users c ON so.closer_id = c.id
            WHERE so.phone = %s OR so.fullname LIKE %s
            ORDER BY so.updated_at DESC
            LIMIT 10
        """, (phone, f"%{phone}%"))
        epem_leads = cur.fetchall()

        # 3. Get tracking history for each lead (last 20 events)
        lead_ids = [r["id"] for r in epem_leads if "error" not in r]
        timelines = {}
        if lead_ids:
            placeholders = ",".join(["%s"] * len(lead_ids))
            cur.execute(f"""
                SELECT sot.sales_opportunity_id, sot.status, sot.observation,
                       sot.created_at, sot.updated_at,
                       sot.attended, sot.sold, sot.reject, sot.reassigned, sot.closer,
                       sot.contact_form, sot.call_again, sot.scheduled_time,
                       u.first_name, u.last_name
                FROM sales_opportunity_trackings sot
                LEFT JOIN users u ON sot.user_id = u.id
                WHERE sot.sales_opportunity_id IN ({placeholders})
                ORDER BY sot.created_at DESC
                LIMIT 200
            """, lead_ids)
            for t in cur.fetchall():
                sid = t["sales_opportunity_id"]
                if sid not in timelines:
                    timelines[sid] = []
                agent = f"{t.get('first_name','')} {t.get('last_name','')}".strip()
                event = {
                    "timestamp": str(t["created_at"]),
                    "status": t.get("status"),
                    "observation": t.get("observation"),
                    "agent": agent or None,
                    "attended": bool(t.get("attended")),
                    "sold": bool(t.get("sold")),
                    "reject": bool(t.get("reject")),
                    "closer": bool(t.get("closer")),
                    "reassigned": bool(t.get("reassigned")),
                    "contact_form": t.get("contact_form"),
                    "call_again": str(t.get("call_again")) if t.get("call_again") else None,
                    "scheduled_time": str(t.get("scheduled_time")) if t.get("scheduled_time") else None,
                }
                timelines[sid].append(event)
        cur.close()
        epem.close()
    except Exception as e:
        epem_leads = [{"error": str(e)}]

    return {
        "query": q,
        "dw_matches": dw_leads,
        "epem_historial": [{
            "id": r["id"],
            "phone": r.get("phone"),
            "fullname": r.get("fullname"),
            "status": r.get("status"),
            "enterprise_id": r.get("enterprise_id"),
            "seller": f"{r.get('first_name','')} {r.get('last_name','')}".strip(),
            "closer": f"{r.get('closer_first','')} {r.get('closer_last','')}".strip() or None,
            "contract_id": r.get("contract_id"),
            "lead_source": r.get("lead"),
            "observation": r.get("observation"),
            "form_id": r.get("form_id"),
            "ad_id": r.get("ad_id"),
            "ad_set_id": r.get("ad_set_id"),
            "city_id": r.get("city_id"),
            "deadline": str(r.get("deadline")),
            "notificated": r.get("notificated"),
            "scheduled": r.get("scheduled"),
            "created_at": str(r.get("created_at")),
            "updated_at": str(r.get("updated_at")),
            "closed_at": str(r.get("closed_at")),
            "selled_at": str(r.get("selled_at")),
            "rejected_at": str(r.get("rejected_at")),
            "rejected_motive_id": r.get("rejected_motive_id"),
            "tracking_history": timelines.get(r["id"], []),
        } for r in epem_leads if "error" not in r],
        "epem_error": epem_leads[0].get("error") if epem_leads and "error" in epem_leads[0] else None,
    }


@router.get("/metricas")
async def dashboard_metricas(
    fecha_desde: str = Query(None), fecha_hasta: str = Query(None),
    db: AsyncSession = Depends(get_db), user: dict = Depends(get_current_user),
):
    """Métricas accionables: funnel, aging, pipeline health, revenue x fuente, eficiencia, trends con Δ%."""
    import pymysql

    conditions, params = _build_filters(fecha_desde, fecha_hasta, None, None, user)
    where = "WHERE " + " AND ".join(conditions) if conditions else ""
    prefix = "AND" if conditions else "WHERE"

    # ── 1. FUNNEL REAL ── leads por status con % drop entre etapas
    funnel = await db.execute(text(f"""
        SELECT status,
               COUNT(*) as leads,
               COUNT(DISTINCT contract_id) FILTER (WHERE (classification_flags->>'es_venta')::int = 1 AND contract_id IS NOT NULL) as ventas
        FROM crm.leads_unificados {where}
        GROUP BY status ORDER BY status"""), params)
    funnel_rows = [dict(r) for r in funnel.mappings().all()]
    funnel_data = {}
    for r in funnel_rows:
        funnel_data[r["status"]] = {"leads": r["leads"], "ventas": r["ventas"]}
    # Calcular % drop entre etapas
    s1 = funnel_data.get(1, {}).get("leads", 0)
    s5 = funnel_data.get(5, {}).get("leads", 0)
    s10 = funnel_data.get(10, {}).get("leads", 0)
    s15 = funnel_data.get(15, {}).get("leads", 0)
    # Funnel real: no es estrictamente secuencial (leads pueden saltar etapas)
    # Métricas clave: % que avanza de 1→5, % que cierra desde 5, % que pasa por 10
    conv_5_to_15 = round(s15 / s5 * 100, 1) if s5 > 0 else 0
    skip_10 = s15 - s10 if s15 > s10 else 0  # leads que cerraron sin pasar por status 10
    funnel_output = {
        "status_1_nuevo": s1,
        "status_5_seguimiento": s5,
        "status_10_cotizado": s10,
        "status_15_venta": s15,
        "activacion_pct": round(s5 / s1 * 100, 1) if s1 > 0 else 0,       # % que sale de status 1
        "cierre_desde_5_pct": conv_5_to_15,                                # % de status 5 que cierra
        "pasan_por_10_pct": round(s10 / s15 * 100, 1) if s15 > 0 else 0,  # % de ventas que pasaron por cotización
        "cierran_sin_cotizar": skip_10,                                     # ventas que saltaron status 10
        "conversion_total_pct": round(s15 / s1 * 100, 1) if s1 > 0 else 0,
    }

    # ── 2. AGING / ABANDONO ── leads stuck en status 1 por días
    aging = await db.execute(text(f"""
        SELECT CASE
                 WHEN first_seen_at < CURRENT_DATE - INTERVAL '30 days' THEN '30+'
                 WHEN first_seen_at < CURRENT_DATE - INTERVAL '15 days' THEN '15-30'
                 WHEN first_seen_at < CURRENT_DATE - INTERVAL '7 days' THEN '7-15'
                 ELSE '<7'
               END as bucket,
               COUNT(*) as leads
        FROM crm.leads_unificados {where}
        {prefix} status = 1
        GROUP BY bucket ORDER BY MIN(first_seen_at)"""), params)
    aging_rows = [dict(r) for r in aging.mappings().all()]
    aging_output = {r["bucket"]: r["leads"] for r in aging_rows}

    # ── 3. TASA DE RESPUESTA ── tiempo first_seen → primer cambio de status
    response_time = await db.execute(text(f"""
        SELECT AVG(EXTRACT(EPOCH FROM (last_updated_at - first_seen_at))/3600)::numeric(10,1) as avg_horas,
               PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY EXTRACT(EPOCH FROM (last_updated_at - first_seen_at))/3600) as median_horas,
               COUNT(*) as total_gestionados
        FROM crm.leads_unificados {where}
        {prefix} status IN (5, 10, 15)
          AND last_updated_at > first_seen_at"""), params)
    rt = dict(response_time.fetchone()._mapping)
    response_output = {
        "avg_horas": float(rt["avg_horas"] or 0),
        "median_horas": float(rt["median_horas"] or 0),
        "total_gestionados": rt["total_gestionados"],
    }

    # ── 4. PIPELINE HEALTH ── % cartera por status, por UN
    pipeline = await db.execute(text(f"""
        SELECT enterprise_id,
               status,
               COUNT(*) as leads,
               ROUND(COUNT(*)::numeric / SUM(COUNT(*)) OVER (PARTITION BY enterprise_id) * 100, 1) as pct
        FROM crm.leads_unificados {where}
        GROUP BY enterprise_id, status ORDER BY enterprise_id, status"""), params)
    pipeline_rows = [dict(r) for r in pipeline.mappings().all()]
    pipeline_by_un = {}
    for r in pipeline_rows:
        eid = r["enterprise_id"]
        if eid not in pipeline_by_un:
            pipeline_by_un[eid] = {"un_nombre": _un_names.get(eid, f"UN {eid}"), "statuses": {}}
        pipeline_by_un[eid]["statuses"][r["status"]] = {"leads": r["leads"], "pct": r["pct"]}

    # ── 5. REVENUE POR FUENTE ── cruce ventas DW × vouchers EPEM
    revenue_fuente = await db.execute(text(f"""
        SELECT SPLIT_PART(COALESCE(classification_flags->>'origen_lead', 'Manual'), '->', 1) as fuente,
               COUNT(*) as leads,
               COUNT(DISTINCT contract_id) FILTER (WHERE (classification_flags->>'es_venta')::int = 1 AND contract_id IS NOT NULL) as ventas,
               CASE WHEN COUNT(*) > 0 THEN ROUND(COUNT(DISTINCT contract_id) FILTER (WHERE (classification_flags->>'es_venta')::int = 1 AND contract_id IS NOT NULL)::numeric/COUNT(*)*100, 1) ELSE 0 END as tasa_conversion
        FROM crm.leads_unificados {where}
        GROUP BY fuente ORDER BY ventas DESC"""), params)
    por_fuente = [dict(r) for r in revenue_fuente.mappings().all()]

    # Revenue EPEM vouchers
    revenue_epem = []
    try:
        conn = pymysql.connect(
            host=settings.EPEM_DB_HOST, port=settings.EPEM_DB_PORT,
            user=settings.EPEM_DB_USER, password=settings.EPEM_DB_PASSWORD,
            database=settings.EPEM_DB_NAME, charset="utf8mb4", connect_timeout=10
        )
        cur = conn.cursor(pymysql.cursors.DictCursor)
        cur.execute("""
            SELECT e.id as enterprise_id, e.name as enterprise_name,
                   COUNT(*) as vouchers,
                   COALESCE(SUM(v.amount), 0) as monto_total
            FROM vouchers v
            JOIN enterprises e ON v.enterprise_id = e.id
            WHERE v.status = 1
            GROUP BY e.id, e.name
            ORDER BY monto_total DESC
        """)
        revenue_epem = [{
            "enterprise_id": r["enterprise_id"],
            "enterprise_name": r["enterprise_name"],
            "vouchers": r["vouchers"],
            "monto_total": int(r["monto_total"]),
            "monto_millones": round(int(r["monto_total"]) / 1_000_000, 1),
        } for r in cur.fetchall()]
        cur.close(); conn.close()
    except Exception as e:
        revenue_epem = [{"error": str(e)[:200]}]

    # ── 6. EFICIENCIA VENDEDOR ── top/bottom performers últimos 30/60/90 días
    def _top_bottom(days: int):
        cutoff = date.today() - timedelta(days=days)
        result = db.execute(text(f"""
            SELECT seller_id,
                   COUNT(*) as leads,
                   COUNT(*) FILTER (WHERE status IN (5,10,15)) as gestionados,
                   COUNT(DISTINCT contract_id) FILTER (WHERE (classification_flags->>'es_venta')::int = 1 AND contract_id IS NOT NULL) as ventas,
                   CASE WHEN COUNT(*) > 0 THEN ROUND(COUNT(DISTINCT contract_id) FILTER (WHERE (classification_flags->>'es_venta')::int = 1 AND contract_id IS NOT NULL)::numeric/COUNT(*)*100, 1) ELSE 0 END as conversion
            FROM crm.leads_unificados
            WHERE first_seen_at >= :cutoff AND seller_id IS NOT NULL
            GROUP BY seller_id HAVING COUNT(*) >= 10
            ORDER BY conversion DESC"""), {"cutoff": cutoff})
        return result

    # Ejecutar las 3 queries secuencialmente (no se pueden paralelizar en async session)
    top30_raw = await _top_bottom(30)
    top60_raw = await _top_bottom(60)
    top90_raw = await _top_bottom(90)

    def _format_performers(result, days_label):
        rows = [dict(r) for r in result.mappings().all()]
        _load_seller_names()
        for r in rows:
            r["fullname"] = _get_seller_name(r["seller_id"])
        top5 = rows[:5]
        bottom5 = rows[-5:] if len(rows) >= 5 else []
        bottom5.reverse()
        return {
            "dias": days_label,
            "top5": top5,
            "bottom5": bottom5,
            "total_vendedores": len(rows),
        }

    performers = {
        "ultimos_30_dias": _format_performers(top30_raw, 30),
        "ultimos_60_dias": _format_performers(top60_raw, 60),
        "ultimos_90_dias": _format_performers(top90_raw, 90),
    }

    # ── 7. VARIACIÓN MENSUAL ── trends con Δ% mes a mes
    trends_result = await db.execute(text(f"""
        SELECT DATE_TRUNC('month', first_seen_at) as mes,
               COUNT(*) as leads,
               COUNT(DISTINCT contract_id) FILTER (WHERE (classification_flags->>'es_venta')::int = 1 AND contract_id IS NOT NULL) as ventas,
               CASE WHEN COUNT(*) > 0 THEN ROUND(COUNT(DISTINCT contract_id) FILTER (WHERE (classification_flags->>'es_venta')::int = 1 AND contract_id IS NOT NULL)::numeric/COUNT(*)*100, 1) ELSE 0 END as tasa_conversion
        FROM crm.leads_unificados
        WHERE first_seen_at >= DATE_TRUNC('month', CURRENT_DATE) - INTERVAL '12 months'
        GROUP BY mes ORDER BY mes"""))
    trends_rows = trends_result.mappings().all()
    trends_mensuales = []
    prev_leads = prev_ventas = None
    for r in trends_rows:
        entry = {
            "mes_str": str(r["mes"])[:7],
            "leads": r["leads"],
            "ventas": r["ventas"],
            "tasa_conversion": r["tasa_conversion"],
        }
        if prev_leads is not None and prev_leads > 0:
            entry["delta_leads_pct"] = round((r["leads"] - prev_leads) / prev_leads * 100, 1)
        else:
            entry["delta_leads_pct"] = None
        if prev_ventas is not None and prev_ventas > 0:
            entry["delta_ventas_pct"] = round((r["ventas"] - prev_ventas) / prev_ventas * 100, 1)
        else:
            entry["delta_ventas_pct"] = None
        trends_mensuales.append(entry)
        prev_leads = r["leads"]
        prev_ventas = r["ventas"]

    # ── 8. CONVERSIÓN POR UN ──
    conv_un = await db.execute(text(f"""
        SELECT enterprise_id, COUNT(*) as leads,
               COUNT(DISTINCT contract_id) FILTER (WHERE (classification_flags->>'es_venta')::int = 1 AND contract_id IS NOT NULL) as ventas,
               CASE WHEN COUNT(*) > 0 THEN ROUND(COUNT(DISTINCT contract_id) FILTER (WHERE (classification_flags->>'es_venta')::int = 1 AND contract_id IS NOT NULL)::numeric/COUNT(*)*100, 1) ELSE 0 END as tasa_conversion,
               COUNT(DISTINCT seller_id) as vendedores_activos
        FROM crm.leads_unificados {where}
        GROUP BY enterprise_id ORDER BY ventas DESC"""), params)
    por_un = [dict(r) for r in conv_un.mappings().all()]

    # ── 9. TIME TO CLOSE ──
    avg_close = await db.execute(text(f"""
        SELECT AVG(EXTRACT(EPOCH FROM (last_updated_at - first_seen_at))/86400)::numeric(10,1) as avg_dias,
               COUNT(*) as total_ventas,
               PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY EXTRACT(EPOCH FROM (last_updated_at - first_seen_at))/86400) as median_dias
        FROM crm.leads_unificados {where}
        WHERE (classification_flags->>'es_venta')::int = 1
          AND last_updated_at IS NOT NULL"""), params)
    time_to_close = dict(avg_close.fetchone()._mapping)

    return {
        "funnel": funnel_output,
        "aging": aging_output,
        "response_time": response_output,
        "pipeline_health": [{
            "enterprise_id": eid,
            "un_nombre": data["un_nombre"],
            "statuses": data["statuses"],
        } for eid, data in sorted(pipeline_by_un.items())],
        "por_fuente": por_fuente,
        "revenue_epem": revenue_epem,
        "performers": performers,
        "trends_mensuales": trends_mensuales,
        "por_un": [{
            "enterprise_id": r["enterprise_id"],
            "un_nombre": _un_names.get(r["enterprise_id"], f"UN {r['enterprise_id']}"),
            "leads": r["leads"], "ventas": r["ventas"],
            "tasa_conversion": r["tasa_conversion"],
            "vendedores_activos": r["vendedores_activos"],
        } for r in por_un],
        "time_to_close": {
            "avg_dias": float(time_to_close["avg_dias"] or 0),
            "total_ventas": time_to_close["total_ventas"],
            "median_dias": float(time_to_close["median_dias"] or 0),
        },
    }


@router.get("/fuentes-comparacion")
async def dashboard_fuentes_comparacion(
    meses: int = Query(12, ge=1, le=36),
    enterprise_id: int = Query(None),
    por_unidad: bool = Query(False),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """Comparacion Botmaker vs ThinkChat (y resto) por mes.
    Para decision de inversion / operacion / auditoria.
    Devuelve series mensuales con leads, gestionados, ventas, conversion y share.
    Si por_unidad=True, devuelve comparativa por unidad de negocio (enterprise_id).
    """
    # Filtros base
    conditions = ["first_seen_at >= DATE_TRUNC('month', CURRENT_DATE) - (:meses || ' months')::interval"]
    params = {"meses": str(meses)}
    if enterprise_id:
        conditions.append("enterprise_id = :enterprise_id")
        params["enterprise_id"] = enterprise_id
    if user.get("role") == "supervisor" and user.get("enterprise_id"):
        conditions.append("enterprise_id = :user_enterprise")
        params["user_enterprise"] = user["enterprise_id"]
    where = "WHERE " + " AND ".join(conditions)

    if por_unidad:
        # Modo comparativa por unidad de negocio
        serie_sql = f"""
            SELECT
                enterprise_id,
                DATE_TRUNC('month', first_seen_at) as mes,
                SPLIT_PART(COALESCE(classification_flags->>'origen_lead', 'Manual'), '->', 1) as fuente,
                COUNT(*) as leads,
                COUNT(*) FILTER (WHERE status IN (5,10,15)) as gestionados,
                COUNT(*) FILTER (WHERE (classification_flags->>'es_venta')::int = 1) as ventas,
                COUNT(DISTINCT contract_id) FILTER (WHERE (classification_flags->>'es_venta')::int = 1) as contratos
            FROM crm.leads_unificados {where}
            GROUP BY enterprise_id, mes, fuente
            ORDER BY mes DESC, enterprise_id, leads DESC
        """
        res = await db.execute(text(serie_sql), params)
        rows = res.fetchall()

        UN_MAP = {1: "Odontologia", 2: "Med. Prepaga", 4: "Emergencias", 5: "Med. Estetica"}

        # Estructura: {enterprise_id: {mes: {fuente: {...}}}}
        unids = {}
        for r in rows:
            eid = r.enterprise_id
            m = r.mes
            f = r.fuente
            if eid not in unids:
                unids[eid] = {
                    "nombre": UN_MAP.get(eid, f"UN {eid}"),
                    "meses": {},
                }
            if m not in unids[eid]["meses"]:
                unids[eid]["meses"][m] = {}
            unids[eid]["meses"][m][f] = {
                "leads": int(r.leads or 0),
                "gestionados": int(r.gestionados or 0),
                "ventas": int(r.ventas or 0),
                "contratos": int(r.contratos or 0),
                "conversion": round((int(r.ventas or 0) / int(r.leads or 0)) * 100, 2) if r.leads else 0,
            }

        # Totales por unidad (acumulado del período)
        totales_por_unidad = {}
        for eid, data in unids.items():
            tot = {"leads": 0, "ventas": 0, "gestionados": 0, "por_fuente": {}}
            for m, fuentes in data["meses"].items():
                for f, v in fuentes.items():
                    tot["leads"] += v["leads"]
                    tot["ventas"] += v["ventas"]
                    tot["gestionados"] += v["gestionados"]
                    if f not in tot["por_fuente"]:
                        tot["por_fuente"][f] = {"leads": 0, "ventas": 0}
                    tot["por_fuente"][f]["leads"] += v["leads"]
                    tot["por_fuente"][f]["ventas"] += v["ventas"]
            tot["conversion"] = round((tot["ventas"] / tot["leads"]) * 100, 2) if tot["leads"] else 0
            totales_por_unidad[data["nombre"]] = tot

        return {
            "modo": "por_unidad",
            "meses_consultados": meses,
            "unidades_negocio": list(unids.keys()),
            "unidades_nombres": UN_MAP,
            "totales_por_unidad": totales_por_unidad,
            "detalle": {
                data["nombre"]: [
                    {"mes": str(m)[:7], "fuentes": fuentes}
                    for m, fuentes in sorted(data["meses"].items())
                ]
                for data in unids.values()
            },
        }

    # Modo normal: por fuente (no por unidad)
    serie_sql = f"""
        SELECT
            DATE_TRUNC('month', first_seen_at) as mes,
            SPLIT_PART(COALESCE(classification_flags->>'origen_lead', 'Manual'), '->', 1) as fuente,
            COUNT(*) as leads,
            COUNT(*) FILTER (WHERE status IN (5,10,15)) as gestionados,
            COUNT(*) FILTER (WHERE (classification_flags->>'es_venta')::int = 1) as ventas,
            COUNT(DISTINCT contract_id) FILTER (WHERE (classification_flags->>'es_venta')::int = 1) as contratos
        FROM crm.leads_unificados {where}
        GROUP BY mes, fuente
        ORDER BY mes DESC, leads DESC
    """
    res = await db.execute(text(serie_sql), params)
    rows = res.fetchall()

    fuentes_set = set()
    serie = {}
    for r in rows:
        m = r.mes
        f = r.fuente
        fuentes_set.add(f)
        if m not in serie:
            serie[m] = {}
        serie[m][f] = {
            "leads": int(r.leads or 0),
            "gestionados": int(r.gestionados or 0),
            "ventas": int(r.ventas or 0),
            "contratos": int(r.contratos or 0),
            "conversion": round((int(r.ventas or 0) / int(r.leads or 0)) * 100, 2) if r.leads else 0,
        }

    totales_por_fuente = {}
    for f in fuentes_set:
        total_leads = sum(serie[m].get(f, {}).get("leads", 0) for m in serie)
        total_ventas = sum(serie[m].get(f, {}).get("ventas", 0) for m in serie)
        total_gestionados = sum(serie[m].get(f, {}).get("gestionados", 0) for m in serie)
        totales_por_fuente[f] = {
            "leads": total_leads,
            "ventas": total_ventas,
            "gestionados": total_gestionados,
            "conversion": round((total_ventas / total_leads) * 100, 2) if total_leads else 0,
            "share_pct": 0,
        }

    total_general = sum(t["leads"] for t in totales_por_fuente.values())
    if total_general > 0:
        for f in totales_por_fuente:
            totales_por_fuente[f]["share_pct"] = round(
                (totales_por_fuente[f]["leads"] / total_general) * 100, 1
            )

    bm = totales_por_fuente.get("Botmaker", {"leads": 0, "ventas": 0, "conversion": 0, "share_pct": 0})
    tc = totales_por_fuente.get("ThinkChat", {"leads": 0, "ventas": 0, "conversion": 0, "share_pct": 0})

    serie_ordenada = []
    for m in sorted(serie.keys()):
        entry = {"mes": str(m)[:7], "fuentes": serie[m]}
        serie_ordenada.append(entry)

    return {
        "modo": "por_fuente",
        "meses_consultados": meses,
        "total_general": total_general,
        "fuentes": sorted(list(fuentes_set)),
        "totales_por_fuente": totales_por_fuente,
        "comparacion_bm_vs_tc": {
            "botmaker": bm,
            "thinkchat": tc,
            "ratio_bm_tc_leads": round(bm["leads"] / tc["leads"], 2) if tc["leads"] else None,
            "ratio_bm_tc_ventas": round(bm["ventas"] / tc["ventas"], 2) if tc["ventas"] else None,
        },
        "serie_mensual": serie_ordenada,
    }


@router.get("/evolucion")
async def dashboard_evolucion(
    desde: str = Query(None, description="YYYY-MM-DD, default = 12 meses atras"),
    hasta: str = Query(None, description="YYYY-MM-DD, default = hoy"),
    enterprise_id: int = Query(None),
    db: AsyncSession = Depends(get_db), user: dict = Depends(get_current_user),
):
    """Serie mensual de leads/ventas por fuente, con conversion + delta vs mes anterior.

    Pensado para graficos: cada mes trae leads, ventas, conversion, share y delta_pct
    para cada fuente (Botmaker, ThinkChat, Manual, Otro).
    """
    # Default range: ultimos 12 meses
    if not hasta:
        hasta = date.today().strftime("%Y-%m-%d")
    if not desde:
        # 12 meses atras
        d = date.today() - timedelta(days=365)
        desde = d.replace(day=1).strftime("%Y-%m-%d")

    # Parsear a date para que asyncpg pueda hacer el bind (no acepta string)
    desde_date = datetime.strptime(desde, "%Y-%m-%d").date()
    hasta_date = (datetime.strptime(hasta, "%Y-%m-%d") + timedelta(days=1)).date()

    conditions = [
        "first_seen_at >= :desde",
        "first_seen_at <= :hasta",
    ]
    params = {"desde": desde_date, "hasta": hasta_date}
    if enterprise_id:
        conditions.append("enterprise_id = :eid")
        params["eid"] = enterprise_id
    where = "WHERE " + " AND ".join(conditions)

    # Una query que agrupa por mes y fuente
    sql = f"""
        SELECT
            DATE_TRUNC('month', first_seen_at) as mes,
            SPLIT_PART(COALESCE(classification_flags->>'origen_lead', 'Manual'), '->', 1) as fuente,
            COUNT(*) as leads,
            COUNT(DISTINCT contract_id) FILTER (WHERE (classification_flags->>'es_venta')::int = 1 AND contract_id IS NOT NULL) as ventas,
            COUNT(DISTINCT seller_id) FILTER (WHERE seller_id IS NOT NULL) as vendedores_activos
        FROM crm.leads_unificados {where}
        GROUP BY mes, fuente
        ORDER BY mes ASC, fuente ASC
    """
    result = await db.execute(text(sql), params)
    raw_rows = result.fetchall()

    # Consolidar por mes
    meses_dict: dict = {}
    fuentes_set: set = set()
    for r in raw_rows:
        mes_key = str(r.mes)[:7]  # 'YYYY-MM'
        fuente = r.fuente
        fuentes_set.add(fuente)
        if mes_key not in meses_dict:
            meses_dict[mes_key] = {"leads": 0, "ventas": 0}
        meses_dict[mes_key]["leads"] += int(r.leads or 0)
        meses_dict[mes_key]["ventas"] += int(r.ventas or 0)

    # Construir serie final con delta_pct, share, etc
    serie = []
    prev_leads = 0
    prev_ventas = 0
    for mes_key in sorted(meses_dict.keys()):
        leads = meses_dict[mes_key]["leads"]
        ventas = meses_dict[mes_key]["ventas"]
        delta_leads_pct = round((leads - prev_leads) / prev_leads * 100, 1) if prev_leads else 0
        delta_ventas_pct = round((ventas - prev_ventas) / prev_ventas * 100, 1) if prev_ventas else 0

        # Per-fuente breakdown para este mes
        fuentes_breakdown = {}
        for r in raw_rows:
            if str(r.mes)[:7] == mes_key:
                f = r.fuente
                f_leads = int(r.leads or 0)
                f_ventas = int(r.ventas or 0)
                fuentes_breakdown[f] = {
                    "leads": f_leads,
                    "ventas": f_ventas,
                    "conversion": round((f_ventas / f_leads) * 100, 2) if f_leads else 0,
                    "share_pct": round((f_leads / leads) * 100, 1) if leads else 0,
                }

        serie.append({
            "mes": mes_key,
            "leads": leads,
            "ventas": ventas,
            "conversion": round((ventas / leads) * 100, 2) if leads else 0,
            "delta_leads_pct": delta_leads_pct,
            "delta_ventas_pct": delta_ventas_pct,
            "fuentes": fuentes_breakdown,
        })
        prev_leads = leads
        prev_ventas = ventas

    # Totales del rango
    tot_leads = sum(m["leads"] for m in serie)
    tot_ventas = sum(m["ventas"] for m in serie)
    tot_conv = round((tot_ventas / tot_leads) * 100, 2) if tot_leads else 0

    # Per-fuente total
    totales_por_fuente = {}
    for f in fuentes_set:
        f_leads = sum(m["fuentes"].get(f, {}).get("leads", 0) for m in serie)
        f_ventas = sum(m["fuentes"].get(f, {}).get("ventas", 0) for m in serie)
        totales_por_fuente[f] = {
            "leads": f_leads,
            "ventas": f_ventas,
            "conversion": round((f_ventas / f_leads) * 100, 2) if f_leads else 0,
            "share_pct": round((f_leads / tot_leads) * 100, 1) if tot_leads else 0,
        }

    return {
        "rango": {"desde": desde, "hasta": hasta},
        "meses_count": len(serie),
        "fuentes": sorted(list(fuentes_set)),
        "totales": {
            "leads": tot_leads,
            "ventas": tot_ventas,
            "conversion": tot_conv,
        },
        "totales_por_fuente": totales_por_fuente,
        "serie_mensual": serie,
    }


# ─────────────────────────────────────────────────────────
# FEED DE ACTIVIDAD — Últimos movimientos unificados
# ─────────────────────────────────────────────────────────

STATUS_LABEL: dict = {1: "Nuevo", 5: "Contactado", 10: "Gestionado", 15: "Vendido", 30: "Descartado"}


def _load_contract_amounts(contract_ids: list[int]) -> dict:
    """Fetch contract amounts from EPEM MySQL for a list of contract IDs."""
    if not contract_ids:
        return {}
    try:
        import pymysql
        conn = pymysql.connect(
            host=settings.EPEM_DB_HOST, port=settings.EPEM_DB_PORT,
            user=settings.EPEM_DB_USER, password=settings.EPEM_DB_PASSWORD,
            database=settings.EPEM_DB_NAME, charset="utf8mb4", connect_timeout=10
        )
        cur = conn.cursor(pymysql.cursors.DictCursor)
        placeholders = ",".join(["%s"] * len(contract_ids))
        cur.execute(
            f"SELECT id, amount FROM contracts WHERE id IN ({placeholders})",
            contract_ids
        )
        amounts = {row["id"]: float(row["amount"] or 0) for row in cur.fetchall()}
        cur.close(); conn.close()
        return amounts
    except Exception as e:
        print(f"[ACTIVIDAD] Failed to load contract amounts: {e}")
        return {}


def _relativo(ts: datetime) -> str:
    """Human-friendly relative timestamp in Spanish."""
    ahora = datetime.now()
    diff = ahora - ts
    mins = int(diff.total_seconds() / 60)
    if mins < 1:
        return "ahora"
    if mins < 60:
        return f"hace {mins} min"
    horas = mins // 60
    if horas < 24:
        return f"hace {horas}h"
    dias = horas // 24
    if dias == 1:
        return "ayer"
    if dias < 7:
        return f"hace {dias} días"
    return ts.strftime("%d/%m %H:%M")


@router.get("/actividad")
async def get_actividad(
    limit: int = Query(50, ge=1, le=200),
    enterprise_id: Optional[int] = Query(None),
    fuente: Optional[str] = Query(None),
    tipo: Optional[str] = Query(None, description="lead_nuevo, gestion, venta"),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """
    Feed unificado de actividad reciente: leads nuevos, gestiones y ventas.
    Cada evento incluye nombres reales de personas y montos de contrato.
    """
    # Build WHERE clauses — separate for direct table vs JOIN
    where_direct = []
    where_join = []
    params = {}

    if enterprise_id:
        where_direct.append("enterprise_id = :enterprise_id")
        where_join.append("lu.enterprise_id = :enterprise_id")
        params["enterprise_id"] = enterprise_id
    if fuente:
        where_direct.append("(classification_flags->>'origen_lead') = :fuente")
        where_join.append("(lu.classification_flags->>'origen_lead') = :fuente")
        params["fuente"] = fuente

    where_sql = " AND ".join(where_direct) if where_direct else "1=1"
    where_sql_lt = " AND ".join(where_join) if where_join else "1=1"

    # Build UNION ALL query
    subqueries = []

    # Tipo 1: lead_nuevo
    if not tipo or tipo == "lead_nuevo":
        subqueries.append(f"""
            SELECT
                'lead_nuevo' as tipo,
                first_seen_at as timestamp,
                id as lead_id,
                fullname,
                normalized_phone as phone,
                enterprise_id,
                COALESCE(classification_flags->>'origen_lead', 'Manual') as fuente,
                seller_id,
                closer_id,
                contract_id,
                status,
                NULL::int as from_status
            FROM crm.leads_unificados
            WHERE {where_sql}
              AND first_seen_at >= NOW() - INTERVAL '7 days'
        """)

    # Tipo 2: gestion
    if not tipo or tipo == "gestion":
        subqueries.append(f"""
            SELECT
                'gestion' as tipo,
                lt.timestamp,
                lu.id as lead_id,
                lu.fullname,
                lu.normalized_phone as phone,
                lu.enterprise_id,
                COALESCE(lu.classification_flags->>'origen_lead', 'Manual') as fuente,
                lt.seller_id,
                lu.closer_id,
                lu.contract_id,
                lt.to_status as status,
                lt.from_status
            FROM crm.lead_tracking lt
            JOIN crm.leads_unificados lu ON lt.lead_id = lu.id
            WHERE {where_sql_lt}
              AND lt.timestamp >= NOW() - INTERVAL '7 days'
        """)

    # Tipo 3: venta
    if not tipo or tipo == "venta":
        subqueries.append(f"""
            SELECT
                'venta' as tipo,
                last_updated_at as timestamp,
                id as lead_id,
                fullname,
                normalized_phone as phone,
                enterprise_id,
                COALESCE(classification_flags->>'origen_lead', 'Manual') as fuente,
                seller_id,
                closer_id,
                contract_id,
                status,
                NULL::int as from_status
            FROM crm.leads_unificados
            WHERE {where_sql}
              AND status = 15
              AND (classification_flags->>'es_venta')::int = 1
              AND last_updated_at >= NOW() - INTERVAL '7 days'
        """)

    if not subqueries:
        return {"eventos": [], "total": 0}

    union_sql = " UNION ALL ".join(subqueries)
    final_sql = f"""
        SELECT * FROM ({union_sql}) AS actividad
        ORDER BY (CASE WHEN tipo = 'venta' THEN 0 ELSE 1 END), timestamp DESC
        LIMIT :limit
    """
    params["limit"] = limit

    result = await db.execute(text(final_sql), params)
    rows = result.fetchall()

    # Collect contract IDs for amount lookup — directo del DW
    contract_ids = [r.contract_id for r in rows if r.contract_id and r.tipo == "venta"]
    amounts = {}
    if contract_ids:
        result_amt = await db.execute(text(
            "SELECT contract_id, amount FROM crm.leads_unificados "
            "WHERE contract_id = ANY(:cids) AND amount IS NOT NULL"
        ), {"cids": contract_ids})
        amounts = {r.contract_id: float(r.amount) for r in result_amt.fetchall()}

    # Build response
    eventos = []
    for r in rows:
        evt = {
            "tipo": r.tipo,
            "timestamp": r.timestamp.isoformat() if r.timestamp else None,
            "relativo": _relativo(r.timestamp) if r.timestamp else "",
            "lead_id": r.lead_id,
            "fullname": r.fullname or "Sin nombre",
            "phone": r.phone or "",
            "enterprise_id": r.enterprise_id,
            "un_nombre": _un_names.get(r.enterprise_id, f"UN {r.enterprise_id}"),
            "fuente": r.fuente or "Manual",
            "vendedor_nombre": _get_seller_name(r.seller_id) if r.seller_id else None,
            "vendedor_id": r.seller_id,
            "cerrador_nombre": _get_seller_name(r.closer_id) if r.closer_id else None,
            "cerrador_id": r.closer_id,
            "status": r.status,
            "status_label": STATUS_LABEL.get(r.status, f"S-{r.status}"),
        }
        if r.tipo == "gestion" and r.from_status is not None:
            evt["from_status"] = r.from_status
            evt["from_status_label"] = STATUS_LABEL.get(r.from_status, f"S-{r.from_status}")
        if r.tipo == "venta" and r.contract_id:
            evt["contract_id"] = r.contract_id
            evt["monto"] = amounts.get(r.contract_id)
        eventos.append(evt)

    return {
        "eventos": eventos,
        "total": len(eventos),
        "filtros": {
            "enterprise_id": enterprise_id,
            "fuente": fuente,
            "tipo": tipo,
            "limit": limit,
        },
    }


@router.get("/actividad/stats")
async def get_actividad_stats(
    enterprise_id: Optional[int] = Query(None),
    fuente: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """
    KPI cards para el feed de actividad: leads, gestiones, ventas y monto del día.
    """
    where_clauses = []
    params = {}
    if enterprise_id:
        where_clauses.append("enterprise_id = :enterprise_id")
        params["enterprise_id"] = enterprise_id
    if fuente:
        where_clauses.append("(classification_flags->>'origen_lead') = :fuente")
        params["fuente"] = fuente
    where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"

    # Leads hoy
    result = await db.execute(text(f"""
        SELECT COUNT(*) FROM crm.leads_unificados
        WHERE {where_sql}
          AND first_seen_at >= CURRENT_DATE
    """), params)
    leads_hoy = result.scalar()

    # Gestiones hoy
    where_join = where_sql.replace("enterprise_id", "lu.enterprise_id").replace("classification_flags", "lu.classification_flags")
    result = await db.execute(text(f"""
        SELECT COUNT(*) FROM crm.lead_tracking lt
        JOIN crm.leads_unificados lu ON lt.lead_id = lu.id
        WHERE {where_join}
          AND lt.timestamp >= CURRENT_DATE
    """), params)
    gestiones_hoy = result.scalar()

    # Ventas hoy
    result = await db.execute(text(f"""
        SELECT COUNT(*) FROM crm.leads_unificados
        WHERE {where_sql}
          AND status = 15
          AND (classification_flags->>'es_venta')::int = 1
          AND contract_date >= CURRENT_DATE
    """), params)
    ventas_hoy = result.scalar()

    # Monto hoy — directo del DW con amount
    result = await db.execute(text(f"""
        SELECT COALESCE(SUM(amount), 0) as monto
        FROM crm.leads_unificados
        WHERE {where_sql}
          AND status = 15
          AND (classification_flags->>'es_venta')::int = 1
          AND contract_date >= CURRENT_DATE
          AND contract_id IS NOT NULL
          AND amount IS NOT NULL
    """), params)
    monto_hoy = float(result.fetchone().monto or 0)

    # Semana (7 días) para contexto
    result = await db.execute(text(f"""
        SELECT COUNT(*) FROM crm.leads_unificados
        WHERE {where_sql}
          AND first_seen_at >= CURRENT_DATE - INTERVAL '7 days'
    """), params)
    leads_semana = result.scalar()

    result = await db.execute(text(f"""
        SELECT COUNT(*) FROM crm.lead_tracking lt
        JOIN crm.leads_unificados lu ON lt.lead_id = lu.id
        WHERE {where_join}
          AND lt.timestamp >= CURRENT_DATE - INTERVAL '7 days'
    """), params)
    gestiones_semana = result.scalar()

    result = await db.execute(text(f"""
        SELECT COUNT(*) FROM crm.leads_unificados
        WHERE {where_sql}
          AND status = 15
          AND (classification_flags->>'es_venta')::int = 1
          AND last_updated_at >= CURRENT_DATE - INTERVAL '7 days'
    """), params)
    ventas_semana = result.scalar()

    return {
        "hoy": {
            "leads": leads_hoy,
            "gestiones": gestiones_hoy,
            "ventas": ventas_hoy,
            "monto": round(monto_hoy, 2),
        },
        "semana": {
            "leads": leads_semana,
            "gestiones": gestiones_semana,
            "ventas": ventas_semana,
        },
    }


# ─────────────────────────────────────────────────────────
# LEAD DETAIL — Detalle completo de un lead por ID
# ─────────────────────────────────────────────────────────

@router.get("/lead/{lead_id}")
async def get_lead_detail(
    lead_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """
    Detalle completo de un lead: datos, timeline de trackings, monto de contrato.
    """
    # Lead data
    result = await db.execute(text("""
        SELECT
            id, normalized_phone, fullname, email, enterprise_id, branch_id,
            seller_id, closer_id, supervisor_id, contract_id, contract_date, amount,
            status, observation,
            classification_flags, first_seen_at, last_updated_at,
            epem_opportunity_id, bm_customer_id, ad_id
        FROM crm.leads_unificados
        WHERE id = :lead_id
    """), {"lead_id": lead_id})
    row = result.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Lead no encontrado")

    lead = {
        "id": row.id,
        "phone": row.normalized_phone,
        "fullname": row.fullname,
        "email": row.email,
        "enterprise_id": row.enterprise_id,
        "un_nombre": _un_names.get(row.enterprise_id, f"UN {row.enterprise_id}"),
        "branch_id": row.branch_id,
        "seller_id": row.seller_id,
        "vendedor_nombre": _get_seller_name(row.seller_id) if row.seller_id else None,
        "closer_id": row.closer_id,
        "cerrador_nombre": _get_seller_name(row.closer_id) if row.closer_id else None,
        "contract_id": row.contract_id,
        "status": row.status,
        "status_label": STATUS_LABEL.get(row.status, f"S-{row.status}"),
        "observation": row.observation,
        "fuente": (row.classification_flags or {}).get("origen_lead", "Manual") if row.classification_flags else "Manual",
        "es_venta": (row.classification_flags or {}).get("es_venta", 0) if row.classification_flags else 0,
        "es_pauta": (row.classification_flags or {}).get("es_pauta", 0) if row.classification_flags else 0,
        "es_botmaker": (row.classification_flags or {}).get("es_botmaker", 0) if row.classification_flags else 0,
        "es_thinkchat": (row.classification_flags or {}).get("es_thinkchat", 0) if row.classification_flags else 0,
        "first_seen_at": row.first_seen_at.isoformat() if row.first_seen_at else None,
        "last_updated_at": row.last_updated_at.isoformat() if row.last_updated_at else None,
        "contract_date": row.contract_date.isoformat() if hasattr(row, 'contract_date') and row.contract_date else None,
        "epem_opportunity_id": row.epem_opportunity_id,
        "bm_customer_id": row.bm_customer_id,
        "ad_id": row.ad_id,
        "supervisor_id": row.supervisor_id if hasattr(row, 'supervisor_id') else None,
        "supervisor_nombre": _get_seller_name(row.supervisor_id) if hasattr(row, 'supervisor_id') and row.supervisor_id else None,
    }

    # Monto del contrato — directo del DW
    if row.contract_id and lead["es_venta"]:
        lead["monto"] = float(row.amount) if hasattr(row, 'amount') and row.amount else None

    # Timeline de trackings
    result = await db.execute(text("""
        SELECT
            timestamp, from_status, to_status, seller_id, source
        FROM crm.lead_tracking
        WHERE lead_id = :lead_id
        ORDER BY timestamp DESC
        LIMIT 50
    """), {"lead_id": lead_id})
    trackings = []
    for t in result.fetchall():
        trackings.append({
            "timestamp": t.timestamp.isoformat() if t.timestamp else None,
            "from_status": t.from_status,
            "from_status_label": STATUS_LABEL.get(t.from_status, f"S-{t.from_status}") if t.from_status else None,
            "to_status": t.to_status,
            "to_status_label": STATUS_LABEL.get(t.to_status, f"S-{t.to_status}") if t.to_status else None,
            "seller_id": t.seller_id,
            "vendedor_nombre": _get_seller_name(t.seller_id) if t.seller_id else None,
            "source": t.source,
        })

    return {"lead": lead, "trackings": trackings}


# ─────────────────────────────────────────────────────────
# VENDEDOR DETAIL — Perfil completo de un vendedor
# ─────────────────────────────────────────────────────────

@router.get("/vendedor/{seller_id}")
async def get_vendedor_detail(
    seller_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """
    Perfil de vendedor: nombre, supervisor, stats 30d, leads recientes, gestiones recientes.
    """
    # Nombre y supervisor desde cachés EPEM
    nombre = _get_seller_name(seller_id)
    _load_supervisor_data()
    supervisor_id = _seller_supervisor_map.get(seller_id)
    supervisor_nombre = _supervisor_names.get(supervisor_id) if supervisor_id else None

    # Stats 30 días
    result = await db.execute(text("""
        SELECT
            COUNT(*) as leads,
            COUNT(*) FILTER (WHERE status IN (5,10,15)) as gestionados,
            COUNT(*) FILTER (WHERE (classification_flags->>'es_venta')::int = 1) as ventas,
            COUNT(*) FILTER (WHERE status = 1) as nuevos,
            COUNT(*) FILTER (WHERE status = 30) as perdidos
        FROM crm.leads_unificados
        WHERE seller_id = :seller_id
          AND first_seen_at >= CURRENT_DATE - INTERVAL '30 days'
    """), {"seller_id": seller_id})
    stats_row = result.fetchone()
    leads = stats_row.leads or 0
    ventas = stats_row.ventas or 0
    conversion = round((ventas / leads) * 100, 2) if leads else 0

    stats = {
        "leads": leads,
        "gestionados": stats_row.gestionados or 0,
        "ventas": ventas,
        "nuevos": stats_row.nuevos or 0,
        "perdidos": stats_row.perdidos or 0,
        "conversion": conversion,
    }

    # Leads recientes (últimos 20)
    result = await db.execute(text("""
        SELECT id, fullname, normalized_phone, enterprise_id,
               COALESCE(classification_flags->>'origen_lead', 'Manual') as fuente,
               status, first_seen_at
        FROM crm.leads_unificados
        WHERE seller_id = :seller_id
        ORDER BY first_seen_at DESC
        LIMIT 20
    """), {"seller_id": seller_id})
    leads_recientes = []
    for r in result.fetchall():
        leads_recientes.append({
            "id": r.id,
            "fullname": r.fullname,
            "phone": r.normalized_phone,
            "enterprise_id": r.enterprise_id,
            "un_nombre": _un_names.get(r.enterprise_id, f"UN {r.enterprise_id}"),
            "fuente": r.fuente or "Manual",
            "status": r.status,
            "status_label": STATUS_LABEL.get(r.status, f"S-{r.status}"),
            "first_seen_at": r.first_seen_at.isoformat() if r.first_seen_at else None,
        })

    # Gestiones recientes (últimas 20)
    result = await db.execute(text("""
        SELECT lt.timestamp, lt.to_status, lu.id as lead_id, lu.fullname, lu.normalized_phone
        FROM crm.lead_tracking lt
        JOIN crm.leads_unificados lu ON lt.lead_id = lu.id
        WHERE lt.seller_id = :seller_id
        ORDER BY lt.timestamp DESC
        LIMIT 20
    """), {"seller_id": seller_id})
    gestiones = []
    for r in result.fetchall():
        gestiones.append({
            "timestamp": r.timestamp.isoformat() if r.timestamp else None,
            "to_status": r.to_status,
            "to_status_label": STATUS_LABEL.get(r.to_status, f"S-{r.to_status}") if r.to_status else None,
            "lead_id": r.lead_id,
            "fullname": r.fullname,
            "phone": r.normalized_phone,
        })

    return {
        "seller_id": seller_id,
        "nombre": nombre,
        "supervisor_id": supervisor_id,
        "supervisor_nombre": supervisor_nombre,
        "stats": stats,
        "leads_recientes": leads_recientes,
        "gestiones": gestiones,
    }


# ─────────────────────────────────────────────────────────
# LEADS — Sección de leads entrantes con desglose por fuente
# ─────────────────────────────────────────────────────────

@router.get("/leads")
async def get_leads(
    dias: int = Query(1, ge=1, le=90, description="Ventana en días (1=hoy, 7=semana, 30=mes)"),
    fuente: Optional[str] = Query(None, description="Botmaker, ThinkChat, Manual"),
    enterprise_id: Optional[int] = Query(None),
    status: Optional[int] = Query(None),
    page: int = Query(1, ge=1, le=100),
    limit: int = Query(50, ge=10, le=200),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """
    Sección de leads entrantes: stats por fuente/UN + tabla paginada.
    """
    where_clauses = [f"first_seen_at >= CURRENT_DATE - INTERVAL '{dias} days'"]
    params = {}

    if enterprise_id:
        where_clauses.append("enterprise_id = :enterprise_id")
        params["enterprise_id"] = enterprise_id
    if fuente:
        where_clauses.append("(classification_flags->>'origen_lead') = :fuente")
        params["fuente"] = fuente
    if status is not None:
        where_clauses.append("status = :status")
        params["status"] = status

    where_sql = " AND ".join(where_clauses)

    # Stats: total + por fuente + por UN
    result = await db.execute(text(f"""
        SELECT
            COUNT(*) as total,
            COUNT(*) FILTER (WHERE (classification_flags->>'origen_lead') = 'Botmaker') as botmaker,
            COUNT(*) FILTER (WHERE (classification_flags->>'origen_lead') LIKE 'ThinkChat%') as thinkchat,
            COUNT(*) FILTER (WHERE (classification_flags->>'origen_lead') = 'Manual') as manual
        FROM crm.leads_unificados
        WHERE {where_sql}
    """), params)
    stats_row = result.fetchone()

    result = await db.execute(text(f"""
        SELECT enterprise_id, COUNT(*) as leads
        FROM crm.leads_unificados
        WHERE {where_sql}
        GROUP BY enterprise_id ORDER BY leads DESC
    """), params)
    por_un = {row.enterprise_id: row.leads for row in result.fetchall()}

    stats = {
        "total": stats_row.total or 0,
        "botmaker": stats_row.botmaker or 0,
        "thinkchat": stats_row.thinkchat or 0,
        "manual": stats_row.manual or 0,
        "por_un": {_un_names.get(k, f"UN {k}"): v for k, v in por_un.items()},
    }

    # Count total for pagination
    result = await db.execute(text(f"SELECT COUNT(*) FROM crm.leads_unificados WHERE {where_sql}"), params)
    total_count = result.scalar()

    # Leads paginados
    offset = (page - 1) * limit
    result = await db.execute(text(f"""
        SELECT
            id, fullname, normalized_phone, enterprise_id,
            COALESCE(classification_flags->>'origen_lead', 'Manual') as fuente,
            status, seller_id, first_seen_at, ad_id
        FROM crm.leads_unificados
        WHERE {where_sql}
        ORDER BY first_seen_at DESC
        LIMIT :limit OFFSET :offset
    """), {**params, "limit": limit, "offset": offset})

    leads = []
    for r in result.fetchall():
        leads.append({
            "id": r.id,
            "fullname": r.fullname or "Sin nombre",
            "phone": r.normalized_phone or "",
            "enterprise_id": r.enterprise_id,
            "un_nombre": _un_names.get(r.enterprise_id, f"UN {r.enterprise_id}"),
            "fuente": r.fuente or "Manual",
            "status": r.status,
            "status_label": STATUS_LABEL.get(r.status, f"S-{r.status}"),
            "vendedor_nombre": _get_seller_name(r.seller_id) if r.seller_id else None,
            "vendedor_id": r.seller_id,
            "first_seen_at": r.first_seen_at.isoformat() if r.first_seen_at else None,
            "ad_id": r.ad_id,
        })

    return {
        "stats": stats,
        "leads": leads,
        "pagination": {
            "page": page,
            "limit": limit,
            "total": total_count,
            "pages": max(1, (total_count + limit - 1) // limit),
        },
        "filtros": {
            "dias": dias,
            "fuente": fuente,
            "enterprise_id": enterprise_id,
            "status": status,
        },
    }


# ─────────────────────────────────────────────────────────
# RESUMEN EJECUTIVO — Agregado por UN, origen, cartera
# ─────────────────────────────────────────────────────────

@router.get("/resumen")
async def get_resumen(
    dias: int = Query(7, ge=1, le=365, description="Ventana en días (legacy)"),
    desde: Optional[str] = Query(None, description="Fecha desde YYYY-MM-DD"),
    hasta: Optional[str] = Query(None, description="Fecha hasta YYYY-MM-DD"),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """
    Resumen ejecutivo: leads ingresados, ventas, cartera fría/caliente,
    por unidad de negocio y por origen. Agregado en una sola query.
    """
    # Rango: si hay desde/hasta, usar fechas exactas; sino, dias
    if desde and hasta:
        where_time = f"first_seen_at >= '{desde}' AND first_seen_at <= '{hasta}'::date + INTERVAL '1 day'"
        where_venta_time = f"contract_date >= '{desde}' AND contract_date <= '{hasta}'::date + INTERVAL '1 day'"
        rango_label = f"{desde} a {hasta}"
    else:
        if dias == 1:
            interval = "CURRENT_DATE"
            rango_label = "hoy"
        else:
            interval = f"CURRENT_DATE - INTERVAL '{dias} days'"
            rango_label = f"{dias} dias"
        where_time = f"first_seen_at >= {interval}"
        where_venta_time = f"contract_date >= {interval}"

    # Totales generales — leads por first_seen_at, ventas por contract_date (DISTINCT contract_id)
    # Externas NO cuentan como leads ni afectan conversion
    result = await db.execute(text(f"""
        SELECT
            (SELECT COUNT(*) FROM crm.leads_unificados WHERE {where_time}
             AND classification_flags->>'origen_lead' != 'Externo') as total_leads,
            (SELECT COUNT(DISTINCT contract_id) FROM crm.leads_unificados
             WHERE status = 15 AND (classification_flags->>'es_venta')::int = 1 AND {where_venta_time}
               AND classification_flags->>'origen_lead' != 'Externo' AND contract_id IS NOT NULL) as ventas_de_leads,
            (SELECT COUNT(DISTINCT contract_id) FROM crm.leads_unificados
             WHERE status = 15 AND (classification_flags->>'es_venta')::int = 1 AND {where_venta_time}
               AND classification_flags->>'origen_lead' = 'Externo' AND contract_id IS NOT NULL) as ventas_externas,
            (SELECT COUNT(DISTINCT contract_id) FROM crm.leads_unificados
             WHERE status = 15 AND (classification_flags->>'es_venta')::int = 1 AND {where_venta_time}
               AND classification_flags->>'tipo_cartera' = 'Caliente' AND contract_id IS NOT NULL) as ventas_calientes,
            (SELECT COUNT(DISTINCT contract_id) FROM crm.leads_unificados
             WHERE status = 15 AND (classification_flags->>'es_venta')::int = 1 AND {where_venta_time}
               AND classification_flags->>'tipo_cartera' = 'Fria' AND contract_id IS NOT NULL) as ventas_frias,
            (SELECT COUNT(*) FROM crm.leads_unificados WHERE {where_time}
               AND classification_flags->>'tipo_cartera' = 'Caliente') as leads_calientes,
            (SELECT COUNT(*) FROM crm.leads_unificados WHERE {where_time}
               AND classification_flags->>'tipo_cartera' = 'Fria') as leads_frias
    """))
    row = result.fetchone()
    total_leads = row.total_leads or 0
    ventas_de_leads = row.ventas_de_leads or 0
    ventas_externas = row.ventas_externas or 0
    total_ventas = ventas_de_leads + ventas_externas
    conversion = round((ventas_de_leads / total_leads) * 100, 2) if total_leads else 0

    # Monto total de ventas — directo del DW con amount (sin query a EPEM)
    result = await db.execute(text(f"""
        SELECT COALESCE(SUM(amount), 0) as monto_total,
               COUNT(DISTINCT contract_id) as total_ventas
        FROM crm.leads_unificados
        WHERE status = 15 AND (classification_flags->>'es_venta')::int = 1
          AND {where_venta_time} AND contract_id IS NOT NULL AND amount IS NOT NULL
    """))
    monto_row = result.fetchone()
    monto_total = float(monto_row.monto_total or 0)

    # Por unidad de negocio — leads por first_seen_at, ventas por contract_date
    # Ventas usan COUNT(DISTINCT contract_id) para no inflar cuando hay múltiples
    # leads con el mismo contract_id (regresiones, re-gestiones, etc.)
    result = await db.execute(text(f"""
        SELECT
            lu.enterprise_id,
            (SELECT COUNT(*) FROM crm.leads_unificados WHERE enterprise_id = lu.enterprise_id AND {where_time}) as leads,
            (SELECT COUNT(DISTINCT contract_id) FROM crm.leads_unificados WHERE enterprise_id = lu.enterprise_id
             AND status = 15 AND (classification_flags->>'es_venta')::int = 1 AND {where_venta_time}
             AND contract_id IS NOT NULL) as ventas,
            (SELECT COUNT(*) FROM crm.leads_unificados WHERE enterprise_id = lu.enterprise_id AND {where_time}
             AND classification_flags->>'tipo_cartera' = 'Caliente') as caliente,
            (SELECT COUNT(*) FROM crm.leads_unificados WHERE enterprise_id = lu.enterprise_id AND {where_time}
             AND classification_flags->>'tipo_cartera' = 'Fria') as fria,
            (SELECT COUNT(DISTINCT contract_id) FROM crm.leads_unificados WHERE enterprise_id = lu.enterprise_id
             AND status = 15 AND (classification_flags->>'es_venta')::int = 1 AND {where_venta_time}
             AND classification_flags->>'tipo_cartera' = 'Caliente' AND contract_id IS NOT NULL) as ventas_calientes,
            (SELECT COUNT(DISTINCT contract_id) FROM crm.leads_unificados WHERE enterprise_id = lu.enterprise_id
             AND status = 15 AND (classification_flags->>'es_venta')::int = 1 AND {where_venta_time}
             AND classification_flags->>'tipo_cartera' = 'Fria' AND contract_id IS NOT NULL) as ventas_frias
        FROM crm.leads_unificados lu
        WHERE lu.enterprise_id IS NOT NULL
        GROUP BY lu.enterprise_id ORDER BY leads DESC
    """))
    por_un = []
    for r in result.fetchall():
        leads = r.leads or 0
        ventas = r.ventas or 0
        # Monto por UN — directo del DW con amount
        result2 = await db.execute(text(f"""
            SELECT COALESCE(SUM(amount), 0) as monto
            FROM crm.leads_unificados
            WHERE enterprise_id = {r.enterprise_id}
              AND status = 15 AND (classification_flags->>'es_venta')::int = 1
              AND {where_venta_time} AND contract_id IS NOT NULL AND amount IS NOT NULL
        """))
        monto_un = float(result2.fetchone().monto or 0)
        por_un.append({
            "enterprise_id": r.enterprise_id,
            "un_nombre": _un_names.get(r.enterprise_id, f"UN {r.enterprise_id}"),
            "leads": leads,
            "ventas": ventas,
            "conversion": round((ventas / leads) * 100, 2) if leads else 0,
            "caliente": r.caliente or 0,
            "fria": r.fria or 0,
            "ventas_calientes": r.ventas_calientes or 0,
            "ventas_frias": r.ventas_frias or 0,
            "monto": round(monto_un, 2),
        })

    # Por origen — ventas usan COUNT(DISTINCT contract_id) para consistencia
    result = await db.execute(text(f"""
        SELECT
            COALESCE(classification_flags->>'origen_lead', 'Manual') as origen,
            COUNT(*) as leads,
            COUNT(DISTINCT contract_id) FILTER (WHERE status = 15 AND (classification_flags->>'es_venta')::int = 1
             AND contract_id IS NOT NULL) as ventas,
            COUNT(*) FILTER (WHERE classification_flags->>'tipo_cartera' = 'Caliente') as caliente,
            COUNT(*) FILTER (WHERE classification_flags->>'tipo_cartera' = 'Fria') as fria
        FROM crm.leads_unificados
        WHERE {where_time}
        GROUP BY origen ORDER BY leads DESC
    """))
    por_origen = []
    for r in result.fetchall():
        leads = r.leads or 0
        ventas = r.ventas or 0
        por_origen.append({
            "origen": r.origen,
            "leads": leads,
            "ventas": ventas,
            "conversion": round((ventas / leads) * 100, 2) if leads else 0,
            "caliente": r.caliente or 0,
            "fria": r.fria or 0,
        })

    # Cartera cruzada por UN
    result = await db.execute(text(f"""
        SELECT
            enterprise_id,
            classification_flags->>'tipo_cartera' as cartera,
            COUNT(*) as total
        FROM crm.leads_unificados
        WHERE {where_time}
        GROUP BY enterprise_id, cartera ORDER BY enterprise_id, cartera
    """))
    cartera_por_un = {}
    for r in result.fetchall():
        un = _un_names.get(r.enterprise_id, f"UN {r.enterprise_id}")
        if un not in cartera_por_un:
            cartera_por_un[un] = {"Caliente": 0, "Fria": 0}
        cartera_por_un[un][r.cartera or "Fria"] = r.total

    return {
        "rango": {"dias": dias, "desde": desde, "hasta": hasta, "label": rango_label},
        "totales": {
            "leads": total_leads,
            "ventas": total_ventas,
            "ventas_de_leads": ventas_de_leads,
            "ventas_externas": ventas_externas,
            "conversion": conversion,
            "monto": round(monto_total, 2),
            "caliente": row.leads_calientes or 0,
            "fria": row.leads_frias or 0,
            "ventas_calientes": row.ventas_calientes or 0,
            "ventas_frias": row.ventas_frias or 0,
        },
        "por_un": por_un,
        "por_origen": por_origen,
        "cartera_por_un": cartera_por_un,
    }
