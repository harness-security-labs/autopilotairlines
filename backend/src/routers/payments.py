import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..models.payment import Payment
from ..models.loyalty import LoyaltyAccount, LoyaltyTransaction
from ..middleware.auth import require_auth

router = APIRouter(prefix="/api/v1/payments", tags=["payments"])

DOLLARS_PER_POINT = 0.01
POINTS_PER_DOLLAR = 10


class PaymentCreate(BaseModel):
    booking_id: str
    amount: float
    method: str = "credit_card"
    card_number: str | None = None
    points_used: int = 0


class PaymentResponse(BaseModel):
    id: str
    booking_id: str
    amount: float
    currency: str
    method: str
    status: str
    transaction_id: str
    points_used: int = 0
    points_earned: int = 0
    points_remaining: int | None = None


@router.post("", response_model=PaymentResponse)
async def process_payment(
    body: PaymentCreate,
    current_user: dict = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    points_used = body.points_used
    points_discount = 0.0

    if points_used > 0:
        result = await db.execute(
            select(LoyaltyAccount).where(LoyaltyAccount.user_id == uuid.UUID(current_user["sub"]))
        )
        account = result.scalar_one_or_none()
        if not account or account.points < points_used:
            raise HTTPException(status_code=400, detail="Insufficient points")

        points_discount = round(points_used * DOLLARS_PER_POINT, 2)
        if points_discount > body.amount:
            points_used = int(body.amount / DOLLARS_PER_POINT)
            points_discount = round(points_used * DOLLARS_PER_POINT, 2)

        account.points -= points_used
        txn = LoyaltyTransaction(
            account_id=account.id,
            points=-points_used,
            transaction_type="payment",
            source=f"Booking {body.booking_id}",
        )
        db.add(txn)

    card_amount = round(body.amount - points_discount, 2)
    method = "points" if card_amount <= 0 else ("points+card" if points_used > 0 else body.method)

    payment = Payment(
        booking_id=uuid.UUID(body.booking_id),
        amount=body.amount,
        method=method,
        transaction_id=f"txn_{uuid.uuid4().hex[:16]}",
        card_last_four=body.card_number[-4:] if body.card_number and card_amount > 0 else None,
    )
    db.add(payment)

    # Earn points on card-paid amount
    points_earned = int(card_amount * POINTS_PER_DOLLAR)
    points_remaining = None
    if points_earned > 0 or points_used > 0:
        if points_used == 0:
            result = await db.execute(
                select(LoyaltyAccount).where(LoyaltyAccount.user_id == uuid.UUID(current_user["sub"]))
            )
            account = result.scalar_one_or_none()
        if account and points_earned > 0:
            account.points += points_earned
            earn_txn = LoyaltyTransaction(
                account_id=account.id,
                points=points_earned,
                transaction_type="earn",
                source=f"Booking {body.booking_id}",
            )
            db.add(earn_txn)
        if account:
            points_remaining = account.points

    await db.commit()
    await db.refresh(payment)

    return PaymentResponse(
        id=str(payment.id),
        booking_id=str(payment.booking_id),
        amount=payment.amount,
        currency=payment.currency,
        method=payment.method,
        status=payment.status,
        transaction_id=payment.transaction_id,
        points_used=points_used,
        points_earned=points_earned,
        points_remaining=points_remaining,
    )
