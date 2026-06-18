"""
CRM Unificado EPEM — ETL CLI entry point
Stage 1 — Run sync from command line
Usage: python -m etl [--full]
"""

import logging
import sys

from etl.sync import run_full_sync, run_incremental_sync

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("crm.etl.cli")

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--full":
        logger.info("Running FULL sync (initial migration)...")
        run_full_sync()
    else:
        logger.info("Running INCREMENTAL sync...")
        run_incremental_sync()
    logger.info("Done.")
