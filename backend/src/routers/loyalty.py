from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..models.loyalty import LoyaltyAccount, LoyaltyTransaction
from ..middleware.auth import require_auth

router = APIRouter(prefix="/api/v1/loyalty", tags=["loyalty"])

POINTS_PER_DOLLAR = 10
DOLLARS_PER_POINT = 0.01


class LoyaltyResponse(BaseModel):
    points: int
    points_earned_12m: int
    points_value: float
    tier: str
    tier_expiry: str | None


class RedeemRequest(BaseModel):
    points: int
    description: str = "Redemption"


@router.get("/balance", response_model=LoyaltyResponse)
async def get_balance(
    current_user: dict = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(LoyaltyAccount).where(LoyaltyAccount.user_id == UUID(current_user["sub"]))
    )
    account = result.scalar_one_or_none()
    if not account:
        return LoyaltyResponse(points=0, points_earned_12m=0, points_value=0, tier="bronze", tier_expiry=None)

    twelve_months_ago = datetime.now(timezone.utc) - timedelta(days=365)
    earned_result = await db.execute(
        select(func.coalesce(func.sum(LoyaltyTransaction.points), 0))
        .where(and_(
            LoyaltyTransaction.account_id == account.id,
            LoyaltyTransaction.points > 0,
            LoyaltyTransaction.created_at >= twelve_months_ago,
        ))
    )
    points_earned_12m = earned_result.scalar() or 0

    return LoyaltyResponse(
        points=account.points,
        points_earned_12m=points_earned_12m,
        points_value=round(account.points * DOLLARS_PER_POINT, 2),
        tier=account.tier,
        tier_expiry=account.tier_expiry.isoformat() if account.tier_expiry else None,
    )


@router.get("/transactions")
async def get_transactions(
    current_user: dict = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(LoyaltyAccount).where(LoyaltyAccount.user_id == UUID(current_user["sub"]))
    )
    account = result.scalar_one_or_none()
    if not account:
        return []

    txn_result = await db.execute(
        select(LoyaltyTransaction)
        .where(LoyaltyTransaction.account_id == account.id)
        .order_by(LoyaltyTransaction.created_at.desc())
        .limit(30)
    )
    transactions = txn_result.scalars().all()
    return [
        {
            "id": str(t.id),
            "points": t.points,
            "transaction_type": t.transaction_type,
            "source": t.source,
            "created_at": t.created_at.isoformat() if t.created_at else None,
        }
        for t in transactions
    ]


@router.post("/redeem")
async def redeem_points(
    body: RedeemRequest,
    current_user: dict = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(LoyaltyAccount).where(LoyaltyAccount.user_id == UUID(current_user["sub"]))
    )
    account = result.scalar_one_or_none()
    if not account:
        raise HTTPException(status_code=404, detail="No loyalty account found")
    if account.points < body.points:
        raise HTTPException(status_code=400, detail="Insufficient points")
    account.points -= body.points
    txn = LoyaltyTransaction(
        account_id=account.id,
        points=-body.points,
        transaction_type="redemption",
        source=body.description,
    )
    db.add(txn)
    await db.commit()
    return {"status": "redeemed", "points_remaining": account.points}
