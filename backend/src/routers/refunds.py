import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..models.booking import Booking
from ..models.payment import Payment
from ..middleware.auth import require_auth
from ..services.card_service import card_service

router = APIRouter(prefix="/api/v1/refunds", tags=["refunds"])


class RefundRequest(BaseModel):
    booking_id: str
    reason: str


class RefundResponse(BaseModel):
    id: str
    booking_id: str
    status: str
    reason: str
    refund_amount: float | None = None


@router.post("", response_model=RefundResponse)
async def request_refund(
    body: RefundRequest,
    current_user: dict = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Booking).where(Booking.id == uuid.UUID(body.booking_id)))
    booking = result.scalar_one_or_none()
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")

    result = await db.execute(
        select(Payment).where(Payment.booking_id == booking.id)
    )
    payment = result.scalar_one_or_none()

    refund_amount = None

    if payment and payment.card_last_four:
        cards = await card_service.list_cards(current_user["sub"])
        target_card = None
        for c in cards:
            if c["card_last_four"] == payment.card_last_four:
                target_card = c
                break

        if target_card:
            await card_service.credit(
                card_id=target_card["id"],
                amount=payment.amount,
                reference_id=str(booking.id),
                description=f"Refund for booking {booking.pnr}",
            )
            refund_amount = payment.amount

    booking.status = "refunded"
    await db.commit()

    return RefundResponse(
        id=str(uuid.uuid4()),
        booking_id=body.booking_id,
        status="approved",
        reason=body.reason,
        refund_amount=refund_amount,
    )
