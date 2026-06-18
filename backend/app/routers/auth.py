"""
CRM Unificado EPEM — Auth Router
JWT authentication — independent from EPEM
"""

from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt, JWTError
from passlib.context import CryptContext
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db

router = APIRouter(prefix="/api/auth", tags=["auth"])
security = HTTPBearer()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class LoginRequest(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: dict


def create_token(user: dict) -> str:
    """Create JWT token for user."""
    payload = {
        "sub": user["email"],
        "fullname": user.get("fullname", user["email"]),
        "role": user.get("role", "vendedor"),
        "enterprise_id": user.get("enterprise_id"),
        "seller_id": user.get("seller_id"),
        "exp": datetime.utcnow() + timedelta(hours=settings.JWT_EXPIRATION_HOURS),
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def decode_token(token: str) -> dict:
    """Decode and validate JWT token."""
    try:
        return jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
    except JWTError:
        raise HTTPException(status_code=401, detail="Token inválido o expirado")


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> dict:
    """Dependency: extract current user from JWT."""
    return decode_token(credentials.credentials)


@router.post("/login", response_model=TokenResponse)
async def login(req: LoginRequest, db: AsyncSession = Depends(get_db)):
    """Authenticate user and return JWT."""
    result = await db.execute(
        text("SELECT * FROM crm.users WHERE email = :email AND is_active = TRUE"),
        {"email": req.email},
    )
    user = result.fetchone()

    if not user:
        raise HTTPException(status_code=401, detail="Credenciales inválidas")

    user_dict = dict(user._mapping)
    if not pwd_context.verify(req.password, user_dict["password_hash"]):
        raise HTTPException(status_code=401, detail="Credenciales inválidas")

    token = create_token(user_dict)
    return TokenResponse(
        access_token=token,
        user={
            "email": user_dict["email"],
            "fullname": user_dict["fullname"],
            "role": user_dict["role"],
        },
    )


@router.get("/me")
async def me(user: dict = Depends(get_current_user)):
    """Return current user info."""
    return {"email": user["sub"], "role": user["role"], "fullname": user.get("fullname")}
