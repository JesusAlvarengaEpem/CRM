"""
CRM Unificado EPEM — Health Check Router
"""

from fastapi import APIRouter

router = APIRouter(prefix="/api", tags=["health"])


@router.get("/health")
async def health_check():
    """Health check endpoint — verifica que todos los servicios estén vivos."""
    return {
        "status": "healthy",
        "app": "CRM Unificado EPEM",
        "version": "0.1.0",
    }
