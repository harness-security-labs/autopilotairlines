import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..models.booking import Booking
from ..middleware.auth import require_auth

router = APIRouter(prefix="/api/v1/refunds", tags=["refunds"])


class RefundRequest(BaseModel):
    booking_id: str
    reason: str


class RefundResponse(BaseModel):
    id: str
    booking_id: str
    status: str
    reason: str


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
    booking.status = "refund_pending"
    await db.commit()
    return RefundResponse(
        id=str(uuid.uuid4()),
        booking_id=body.booking_id,
        status="approved",
        reason=body.reason,
    )
