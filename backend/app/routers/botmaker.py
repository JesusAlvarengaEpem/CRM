"""
Botmaker Outbound API Router
POST /api/botmaker/send — Send WhatsApp message via Botmaker API
"""
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from typing import Optional
import httpx

from app.routers.auth import get_current_user

router = APIRouter(prefix="/api/botmaker", tags=["botmaker"])

BOTMAKER_API_URL = "https://go.botmaker.com/api/v1.0/message/send"
BOTMAKER_API_KEY = None  # Set via environment: BOTMAKER_API_KEY


class SendMessageRequest(BaseModel):
    phone: str  # Normalized phone (595XXXXXXXXX)
    text: str
    chat_channel_id: Optional[str] = None


@router.post("/send")
async def botmaker_send_message(req: SendMessageRequest, user: dict = Depends(get_current_user)):
    """Send WhatsApp message via Botmaker API."""
    api_key = BOTMAKER_API_KEY
    if not api_key:
        return {"status": "error", "message": "BOTMAKER_API_KEY not configured"}

    async with httpx.AsyncClient(timeout=15) as client:
        try:
            resp = await client.post(
                BOTMAKER_API_URL,
                headers={
                    "access-token": api_key,
                    "Content-Type": "application/json",
                },
                json={
                    "chatChannelNumber": req.chat_channel_id or "",
                    "chatPlatform": "whatsapp",
                    "contactNumber": req.phone,
                    "text": req.text,
                },
            )
            if resp.status_code == 200:
                return {"status": "success", "message": "Mensaje enviado", "phone": req.phone}
            return {"status": "error", "message": f"Botmaker API error: {resp.status_code}", "detail": resp.text[:200]}
        except Exception as e:
            return {"status": "error", "message": str(e)[:200]}
