from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID

from ..database import get_db
from ..models.user import User
from ..middleware.auth import require_auth

router = APIRouter(prefix="/api/v1/users", tags=["users"])


class UserResponse(BaseModel):
    id: str
    email: str
    name: str
    role: str
    phone: str | None
    ssn: str | None
    credit_card: str | None
    date_of_birth: str | None
    loyalty_tier: str


class UserUpdate(BaseModel):
    name: str | None = None
    phone: str | None = None
    role: str | None = None
    loyalty_tier: str | None = None


@router.get("/me", response_model=UserResponse)
async def get_me(
    current_user: dict = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(User).where(User.id == UUID(current_user["sub"])))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return UserResponse(
        id=str(user.id),
        email=user.email,
        name=user.name,
        role=user.role,
        phone=user.phone,
        ssn=user.ssn,
        credit_card=user.credit_card,
        date_of_birth=user.date_of_birth.isoformat() if user.date_of_birth else None,
        loyalty_tier=user.loyalty_tier,
    )


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: str,
    current_user: dict = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(User).where(User.id == UUID(user_id)))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return UserResponse(
        id=str(user.id),
        email=user.email,
        name=user.name,
        role=user.role,
        phone=user.phone,
        ssn=user.ssn,
        credit_card=user.credit_card,
        date_of_birth=user.date_of_birth.isoformat() if user.date_of_birth else None,
        loyalty_tier=user.loyalty_tier,
    )


@router.put("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: str,
    body: UserUpdate,
    current_user: dict = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(User).where(User.id == UUID(user_id)))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    update_data = body.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(user, key, value)
    await db.commit()
    await db.refresh(user)
    return UserResponse(
        id=str(user.id),
        email=user.email,
        name=user.name,
        role=user.role,
        phone=user.phone,
        ssn=user.ssn,
        credit_card=user.credit_card,
        date_of_birth=user.date_of_birth.isoformat() if user.date_of_birth else None,
        loyalty_tier=user.loyalty_tier,
    )
