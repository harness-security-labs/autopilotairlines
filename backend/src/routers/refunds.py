import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..models.booking import Booking
from ..models.payment import Payment, RefundRecord
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


class RefundRecordResponse(BaseModel):
    id: str
    booking_id: str
    pnr: str
    action_type: str
    amount: float
    currency: str
    reason: str | None
    refund_method: str | None
    card_last_four: str | None
    status: str
    processed_at: str


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
    refund_method = None

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
            refund_method = "card"

    booking.status = "refunded"

    record = RefundRecord(
        booking_id=booking.id,
        user_id=uuid.UUID(current_user["sub"]),
        action_type="refund",
        amount=refund_amount or 0,
        reason=body.reason,
        refund_method=refund_method or "card",
        card_last_four=payment.card_last_four if payment else None,
        status="completed",
        pnr=booking.pnr,
    )
    db.add(record)
    await db.commit()

    return RefundResponse(
        id=str(record.id),
        booking_id=body.booking_id,
        status="approved",
        reason=body.reason,
        refund_amount=refund_amount,
    )


@router.get("/history/{pnr}", response_model=list[RefundRecordResponse])
async def get_refund_history(
    pnr: str,
    current_user: dict = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(RefundRecord)
        .where(RefundRecord.pnr == pnr.upper())
        .order_by(RefundRecord.processed_at.desc())
    )
    records = result.scalars().all()

    return [
        RefundRecordResponse(
            id=str(r.id),
            booking_id=str(r.booking_id),
            pnr=r.pnr,
            action_type=r.action_type,
            amount=r.amount,
            currency=r.currency,
            reason=r.reason,
            refund_method=r.refund_method,
            card_last_four=r.card_last_four,
            status=r.status,
            processed_at=r.processed_at.isoformat() if r.processed_at else "",
        )
        for r in records
    ]


@router.get("/history", response_model=list[RefundRecordResponse])
async def get_my_refund_history(
    action_type: str | None = Query(None, description="Filter by 'refund' or 'cancellation'"),
    current_user: dict = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    query = (
        select(RefundRecord)
        .where(RefundRecord.user_id == uuid.UUID(current_user["sub"]))
    )
    if action_type:
        query = query.where(RefundRecord.action_type == action_type)
    query = query.order_by(RefundRecord.processed_at.desc()).limit(20)

    result = await db.execute(query)
    records = result.scalars().all()

    return [
        RefundRecordResponse(
            id=str(r.id),
            booking_id=str(r.booking_id),
            pnr=r.pnr,
            action_type=r.action_type,
            amount=r.amount,
            currency=r.currency,
            reason=r.reason,
            refund_method=r.refund_method,
            card_last_four=r.card_last_four,
            status=r.status,
            processed_at=r.processed_at.isoformat() if r.processed_at else "",
        )
        for r in records
    ]
