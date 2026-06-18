"""
CRM Unificado EPEM — ETL Router (manual sync trigger)
"""

from fastapi import APIRouter
import threading
from etl.sync import run_full_sync, run_incremental_sync
from etl.thinkchat_sync import run_thinkchat_sync

router = APIRouter(prefix="/api/etl", tags=["etl"])


@router.post("/sync")
async def trigger_incremental_sync():
    """Manually trigger an incremental sync."""
    result = run_incremental_sync()
    return {"status": "ok", "result": result}


@router.post("/sync/full")
async def trigger_full_sync():
    """Manually trigger a full sync (initial migration)."""
    result = run_full_sync()
    return {"status": "ok", "result": result}


@router.post("/sync/thinkchat")
async def trigger_thinkchat_sync():
    """Manually trigger a ThinkChat ETL sync.
    Auto-descarga el Excel del portal si no existe, lo parsea, y upserts al DW.
    """
    from etl.thinkchat_sync import run_thinkchat_sync_from_excel
    result = run_thinkchat_sync_from_excel()
    return {"status": result.get("status", "ok"), "result": result}


@router.post("/sync/todo")
async def trigger_sync_todo():
    """Sync completo: leads + trackings inmediato, ThinkChat en thread separado.
    Un solo botón para actualizar todo. ThinkChat tarda ~60s — se lanza en thread
    y el frontend auto-refresca para capturarlo.
    """
    from etl.thinkchat_sync import run_thinkchat_sync_from_excel

    # 1. Leads + trackings (rápido, ~2s)
    result = run_incremental_sync()
    leads_upserted = result.get("records_upserted", 0)
    trackings_upserted = result.get("trackings_upserted", 0)

    # 2. Externas (contracts sin match ThinkChat/Botmaker)
    from etl.sync import run_externas_sync
    externas_result = run_externas_sync()
    externas_upserted = externas_result.get("externas_upserted", 0)

    # 3. ThinkChat en thread separado (~60s)
    threading.Thread(target=run_thinkchat_sync_from_excel, daemon=True).start()

    return {
        "status": "ok",
        "leads": leads_upserted,
        "gestiones": trackings_upserted,
        "externas": externas_upserted,
        "thinkchat": "pending",
        "message": f"{leads_upserted} leads, {trackings_upserted} gestiones, {externas_upserted} externas sincronizados. ThinkChat en background.",
    }
