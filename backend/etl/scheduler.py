"""
CRM Unificado EPEM — ETL Scheduler
Stage 1 — APScheduler for periodic sync
"""

import logging
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from app.core.config import settings
from etl.sync import run_incremental_sync, run_externas_sync
from etl.thinkchat_sync import run_thinkchat_sync_from_excel

logger = logging.getLogger("crm.scheduler")

scheduler = BackgroundScheduler()


def start_scheduler():
    """Start the ETL scheduler.
    - Main sync: cada SYNC_INTERVAL_MINUTES (default 60)
    - ThinkChat sync: diario a las 04:00 America/Asuncion (auto-descarga Excel + UPSERT)
    - Externas sync: diario a las 04:30 America/Asuncion (importa contracts EPEM sin ThinkChat/Botmaker match)
      CRM-FIX-1: antes no estaba programado — solo corria manual. Los contracts creados
      despues de la ultima corrida manual no se reimportaban.
    """
    interval = settings.SYNC_INTERVAL_MINUTES

    scheduler.add_job(
        run_incremental_sync,
        "interval",
        minutes=interval,
        id="etl_sync",
        replace_existing=True,
    )
    # ThinkChat: diario a las 04:00 hora Asuncion
    scheduler.add_job(
        run_thinkchat_sync_from_excel,
        CronTrigger(hour=4, minute=0, timezone="America/Asuncion"),
        id="thinkchat_sync",
        replace_existing=True,
        misfire_grace_time=3600,  # 1h de gracia si el server estuvo down
    )
    # CRM-FIX-1: Externas sync diario a las 04:30 — despues de ThinkChat para que el filtro
    # de "contracts ya en DW" tenga los ThinkChat actualizados primero
    scheduler.add_job(
        run_externas_sync,
        CronTrigger(hour=4, minute=30, timezone="America/Asuncion"),
        id="externas_sync",
        replace_existing=True,
        misfire_grace_time=3600,
    )
    scheduler.start()
    logger.info(
        f"ETL scheduler started — main sync every {interval} min, "
        f"ThinkChat sync daily at 04:00 America/Asuncion"
    )


def stop_scheduler():
    """Stop the ETL scheduler."""
    scheduler.shutdown(wait=False)
    logger.info("ETL scheduler stopped")
