import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..middleware.auth import require_auth

router = APIRouter(prefix="/api/v1/baggage", tags=["baggage"])

BAGGAGE_RECORDS: dict[str, list[dict]] = {}


class BaggageRequest(BaseModel):
    booking_id: str
    weight_kg: float
    bag_type: str = "checked"
    description: str = ""


class BaggageResponse(BaseModel):
    tag_id: str
    booking_id: str
    weight_kg: float
    bag_type: str
    fee: float
    status: str


@router.post("", response_model=BaggageResponse)
async def add_baggage(
    body: BaggageRequest,
    current_user: dict = Depends(require_auth),
):
    fee = 0.0
    if body.bag_type == "checked":
        fee = 35.0 if body.weight_kg <= 23 else 75.0
    elif body.bag_type == "oversized":
        fee = 100.0

    tag_id = f"BAG-{uuid.uuid4().hex[:8].upper()}"
    record = {
        "tag_id": tag_id,
        "booking_id": body.booking_id,
        "weight_kg": body.weight_kg,
        "bag_type": body.bag_type,
        "fee": fee,
        "status": "checked",
        "description": body.description,
    }

    if body.booking_id not in BAGGAGE_RECORDS:
        BAGGAGE_RECORDS[body.booking_id] = []
    BAGGAGE_RECORDS[body.booking_id].append(record)

    return BaggageResponse(**{k: v for k, v in record.items() if k != "description"})


@router.get("/{booking_id}")
async def get_baggage(booking_id: str):
    bags = BAGGAGE_RECORDS.get(booking_id, [])
    return {"booking_id": booking_id, "bags": bags, "total_fees": sum(b["fee"] for b in bags)}
