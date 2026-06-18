"""
thinkchat_portal.py — Cliente del portal ThinkChat (autodescarga de Excel).
REPLICA EXACTA de thinkchat_dashboard/thinkchat_browser_agent/portal_client.py
Adaptado solo en nombres de clase/métodos para compatibilidad con el ETL del CRM.
"""
from __future__ import annotations

import logging
import os
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

import requests

logger = logging.getLogger("crm.etl.thinkchat_portal")

# ── Portal URLs ────────────────────────────────────────────────────────────────
PORTAL_BASE = "https://epem.whatsapp.net.py/thinkcomm-x/"
LOGIN_URL = PORTAL_BASE + "app.login/back/auth.php?action=login"
SESSION_URL = PORTAL_BASE + "app.ws/back/get-session.php?action=session_get"
EXPORT_URL = PORTAL_BASE + "app.reportes/report.pautas/export-excel.php"
LEADS_EXPORT_URL = PORTAL_BASE + "app.leads/back/export-excel.php"

# ── Constants (replica exacta de config.py) ────────────────────────────────────
AD_ID_ALL = "999"
ANNUAL_START_DATE = "2025-01-01"
DOWNLOAD_TIMEOUT = 60
LOGIN_TIMEOUT = 15
LOGIN_RETRIES = 3
LOGIN_BACKOFF = 2
DOWNLOAD_RETRIES = 2

# ── Paths ──────────────────────────────────────────────────────────────────────
DOWNLOAD_DIR = Path(__file__).parent.parent.parent / "data"
PAUTAS_FILE = DOWNLOAD_DIR / "Pautas-ThinkChat-anho.xlsx"
FORMULARIOS_FILE = DOWNLOAD_DIR / "Leads-ThinkChat-anho.xlsx"


class PortalError(Exception):
    """Base error for portal operations."""


class LoginFailed(PortalError):
    """Could not authenticate with the portal."""


class ThinkChatPortalClient:
    """Stateless-ish client: creates a fresh session per use.
    REPLICA EXACTA de PortalClient del dashboard."""

    def __init__(self, user: str | None = None, password: str | None = None):
        self.user = user or os.getenv("TC_PORTAL_USER", "")
        self.password = password or os.getenv("TC_PORTAL_PASS", "")
        if not self.user or not self.password:
            raise LoginFailed("TC_PORTAL_USER y TC_PORTAL_PASS deben estar configurados en .env")
        self._session: Optional[requests.Session] = None
        self._user_info: Optional[dict] = None

    @property
    def session(self) -> requests.Session:
        """Authenticated requests session (lazy login)."""
        if self._session is None:
            self.login()
        return self._session

    @property
    def user_info(self) -> dict:
        """User info from last login."""
        if self._user_info is None:
            self.login()
        return self._user_info

    # ── Login (REPLICA EXACTA) ─────────────────────────────────────────────────

    def login(self) -> dict:
        """Authenticate with the portal. Retries on failure."""
        for attempt in range(1, LOGIN_RETRIES + 1):
            try:
                s = requests.Session()
                s.headers.update({
                    "User-Agent": "ThinkChatAgent/1.0 (EPEM Bot)"
                })

                logger.info(f"Login attempt {attempt}/{LOGIN_RETRIES}")
                r = s.post(LOGIN_URL, json={"user": self.user, "pass": self.password}, timeout=LOGIN_TIMEOUT)

                if r.status_code != 200:
                    raise LoginFailed(f"HTTP {r.status_code}")

                data = r.json()
                if not data.get("user_id"):
                    raise LoginFailed(f"No user_id in response: {r.text[:200]}")

                # Verify session works
                sr = s.get(SESSION_URL, timeout=LOGIN_TIMEOUT)
                session_data = sr.json()
                if not session_data.get("user_id"):
                    raise LoginFailed("Session verification failed")

                self._session = s
                self._user_info = data
                logger.info(f"Login OK — user_id={data.get('user_id')}, grupo={data.get('grupo_nombre')}")
                return data

            except (LoginFailed, requests.RequestException) as e:
                logger.warning(f"Login attempt {attempt} failed: {e}")
                if attempt < LOGIN_RETRIES:
                    time.sleep(LOGIN_BACKOFF * attempt)
                else:
                    raise LoginFailed(f"All {LOGIN_RETRIES} login attempts failed: {e}")

    # ── Downloads (REPLICA EXACTA) ─────────────────────────────────────────────

    def download_pautas(self, ad_id: str, fd: str, fh: str,
                        empresa: str = "") -> bytes:
        """
        Download pautas Excel from portal.

        Args:
            ad_id:   "999" for all, or specific Meta AD ID
            fd:      fecha desde (YYYY-MM-DD)
            fh:      fecha hasta (YYYY-MM-DD)
            empresa: source ID for filtering ("" = all, "1" = Epem, etc.)

        Returns:
            Raw XLSX bytes.
        """
        params = {
            "ad_id": ad_id,
            "fd": fd,
            "fh": fh,
            "empresa": empresa,
        }

        for attempt in range(1, DOWNLOAD_RETRIES + 1):
            try:
                logger.info(f"Downloading pautas: ad_id={ad_id}, fd={fd}, fh={fh}, empresa={empresa or '(all)'}")
                r = self.session.get(EXPORT_URL, params=params, timeout=DOWNLOAD_TIMEOUT)

                if r.status_code != 200:
                    raise PortalError(f"HTTP {r.status_code}")

                content_type = r.headers.get("content-type", "")
                if len(r.content) < 100:
                    logger.warning(f"Tiny response ({len(r.content)} bytes) — may be empty")

                logger.info(f"Downloaded {len(r.content):,} bytes (type: {content_type})")
                return r.content

            except requests.RequestException as e:
                logger.warning(f"Download attempt {attempt} failed: {e}")
                if attempt < DOWNLOAD_RETRIES:
                    time.sleep(2)
                else:
                    raise PortalError(f"Download failed after {DOWNLOAD_RETRIES} attempts: {e}")

    def download_yearly(self, fh: str) -> bytes:
        """Download full-year pautas for all sources. fh = closed day."""
        return self.download_pautas(ad_id=AD_ID_ALL, fd=ANNUAL_START_DATE, fh=fh, empresa="")

    def download_by_source(self, source_id: int, fd: str, fh: str) -> bytes:
        """Download pautas for a specific source within a date range."""
        return self.download_pautas(ad_id=AD_ID_ALL, fd=fd, fh=fh, empresa=str(source_id))

    # ── CRM-compatible wrappers ────────────────────────────────────────────────

    def download_yearly_pautas(self) -> Path:
        """Descarga el Excel anual completo y lo guarda en DOWNLOAD_DIR. Retorna el path.
        Wrapper compatible con el ETL del CRM."""
        tz = timezone(timedelta(hours=-3))  # America/Asuncion
        fh = (datetime.now(tz) - timedelta(days=1)).strftime("%Y-%m-%d")
        content = self.download_yearly(fh=fh)
        DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
        PAUTAS_FILE.write_bytes(content)
        logger.info(f"Pautas saved to {PAUTAS_FILE} ({len(content):,} bytes)")
        return PAUTAS_FILE

    # ── Cleanup ────────────────────────────────────────────────────────────────

    def close(self):
        """Close the session."""
        if self._session:
            self._session.close()
            self._session = None
            self._user_info = None

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
