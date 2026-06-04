import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..models.payment import Payment
from ..models.loyalty import LoyaltyAccount, LoyaltyTransaction
from ..middleware.auth import require_auth
from ..services.card_service import card_service

router = APIRouter(prefix="/api/v1/payments", tags=["payments"])

from ..constants import DOLLARS_PER_POINT, POINTS_PER_DOLLAR, compute_tier
from ..models.user import User


class PaymentCreate(BaseModel):
    booking_id: str
    amount: float
    method: str = "credit_card"
    payment_method_id: str | None = None
    card_number: str | None = None
    cvv: str | None = None
    expiry_month: int | None = None
    expiry_year: int | None = None
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

    card_last_four = None

    if card_amount > 0 and body.payment_method_id:
        if not body.cvv or not body.expiry_month or not body.expiry_year:
            raise HTTPException(status_code=400, detail="CVV and expiry required for card payment")
        try:
            await card_service.charge(
                card_id=body.payment_method_id,
                amount=card_amount,
                cvv=body.cvv,
                expiry_month=body.expiry_month,
                expiry_year=body.expiry_year,
                reference_id=body.booking_id,
                description=f"Payment for booking {body.booking_id}",
            )
        except HTTPException as e:
            if e.status_code == 402:
                raise HTTPException(status_code=402, detail=e.detail)
            raise
        cards = await card_service.list_cards(current_user["sub"])
        for c in cards:
            if c["id"] == body.payment_method_id:
                card_last_four = c["card_last_four"]
                break
    elif card_amount > 0 and body.card_number:
        card_last_four = body.card_number[-4:]

    transaction_id = f"txn_{uuid.uuid4().hex[:16]}"

    payment = Payment(
        booking_id=uuid.UUID(body.booking_id),
        amount=body.amount,
        method=method,
        transaction_id=transaction_id,
        card_last_four=card_last_four,
    )
    db.add(payment)

    points_remaining = None
    if points_used == 0:
        result = await db.execute(
            select(LoyaltyAccount).where(LoyaltyAccount.user_id == uuid.UUID(current_user["sub"]))
        )
        account = result.scalar_one_or_none()

    tier = account.tier if account else "bronze"
    earn_rate = POINTS_PER_DOLLAR.get(tier, 1)
    points_earned = int(card_amount * earn_rate)

    if points_earned > 0 or points_used > 0:
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

    if account and points_earned > 0:
        from datetime import datetime, timedelta, timezone
        from sqlalchemy import func, and_
        twelve_months_ago = datetime.now(timezone.utc) - timedelta(days=365)
        earned_result = await db.execute(
            select(func.coalesce(func.sum(LoyaltyTransaction.points), 0))
            .where(and_(
                LoyaltyTransaction.account_id == account.id,
                LoyaltyTransaction.points > 0,
                LoyaltyTransaction.created_at >= twelve_months_ago,
            ))
        )
        total_earned_12m = (earned_result.scalar() or 0) + points_earned
        new_tier = compute_tier(total_earned_12m)
        if account.tier != new_tier:
            account.tier = new_tier
            user_result = await db.execute(select(User).where(User.id == uuid.UUID(current_user["sub"])))
            user = user_result.scalar_one_or_none()
            if user:
                user.loyalty_tier = new_tier

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
