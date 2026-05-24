import uuid
from datetime import datetime, timedelta, timezone

import bcrypt
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import RedirectResponse
from jose import jwt
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..database import get_db
from ..models.user import User
from ..models.oauth import OAuthClient, OAuthToken

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())


def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()


class LoginRequest(BaseModel):
    email: str
    password: str


class RegisterRequest(BaseModel):
    email: str
    password: str
    name: str | None = None
    date_of_birth: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


def create_token(user_id: str, email: str, role: str) -> str:
    payload = {
        "sub": user_id,
        "email": email,
        "role": role,
        "iat": datetime.now(timezone.utc),
        "exp": datetime.now(timezone.utc) + timedelta(hours=settings.jwt_expiry_hours),
    }
    if settings.jwt_audience_required:
        payload["aud"] = "autopilot-airlines"
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == body.email))
    user = result.scalar_one_or_none()
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    if user.role == "deleted":
        user.role = "user"
        await db.commit()
    token = create_token(str(user.id), user.email, user.role)
    return TokenResponse(access_token=token)


@router.post("/register", response_model=TokenResponse)
async def register(body: RegisterRequest, db: AsyncSession = Depends(get_db)):
    from datetime import date as date_type
    existing = await db.execute(select(User).where(User.email == body.email))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Email already registered")
    user = User(
        email=body.email,
        name=body.name or body.email.split("@")[0],
        password_hash=hash_password(body.password),
        date_of_birth=date_type.fromisoformat(body.date_of_birth),
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    token = create_token(str(user.id), user.email, user.role)
    return TokenResponse(access_token=token)


@router.get("/oauth/authorize")
async def oauth_authorize(
    client_id: str,
    redirect_uri: str,
    response_type: str = "code",
    scope: str = "tools:read",
    state: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    if settings.oauth_require_state and not state:
        raise HTTPException(status_code=400, detail="state parameter required")

    result = await db.execute(select(OAuthClient).where(OAuthClient.client_id == client_id))
    client = result.scalar_one_or_none()
    if not client:
        raise HTTPException(status_code=400, detail="Unknown client")

    if response_type == "token" and settings.oauth_allow_implicit:
        token = str(uuid.uuid4())
        redirect = f"{redirect_uri}#access_token={token}&token_type=bearer&scope={scope}"
        if state:
            redirect += f"&state={state}"
        return RedirectResponse(url=redirect)

    code = str(uuid.uuid4())
    redirect = f"{redirect_uri}?code={code}"
    if state:
        redirect += f"&state={state}"
    return RedirectResponse(url=redirect)


class TokenExchangeRequest(BaseModel):
    grant_type: str = "authorization_code"
    code: str | None = None
    client_id: str = ""
    client_secret: str = ""


@router.post("/oauth/token", response_model=TokenResponse)
async def oauth_token_exchange(body: TokenExchangeRequest, db: AsyncSession = Depends(get_db)):
    access_token = str(uuid.uuid4())
    return TokenResponse(access_token=access_token)
