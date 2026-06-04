import random
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..models.booking import Booking
from ..models.flight import Flight
from ..middleware.auth import get_current_user

router = APIRouter(prefix="/api/v1/checkin", tags=["checkin"])


class CheckInRequest(BaseModel):
    booking_id: str
    seat_preference: str | None = None


class BoardingPass(BaseModel):
    booking_id: str
    pnr: str
    passenger_name: str
    seat: str
    gate: str
    boarding_group: str
    boarding_pass_url: str
    flight_number: str | None = None
    origin: str | None = None
    destination: str | None = None
    departure: str | None = None
    arrival: str | None = None
    boarding_time: str | None = None
    travel_date: str | None = None
    aircraft: str | None = None
    cabin_class: str | None = None


def _generate_seat(preference: str | None) -> str:
    row = random.randint(1, 30)
    if preference == "window":
        col = random.choice("AF")
    elif preference == "aisle":
        col = random.choice("CD")
    else:
        col = random.choice("BE")
    return f"{row}{col}"


@router.post("", response_model=BoardingPass)
async def check_in(
    body: CheckInRequest,
    current_user: dict | None = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Booking).where(Booking.id == uuid.UUID(body.booking_id))
    )
    booking = result.scalar_one_or_none()
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")

    flight_result = await db.execute(
        select(Flight).where(Flight.id == booking.flight_id)
    )
    flight = flight_result.scalar_one_or_none()

    if flight and booking.travel_date:
        from .flights import project_flight_to_date
        dep, _ = project_flight_to_date(flight, booking.travel_date)
        now = datetime.now(timezone.utc)
        if dep.tzinfo is None:
            dep = dep.replace(tzinfo=timezone.utc)
        hours_until = (dep - now).total_seconds() / 3600
        if hours_until > 48:
            raise HTTPException(
                status_code=400,
                detail="Check-in opens 48 hours before departure",
            )

    seat = _generate_seat(body.seat_preference)
    gate = f"{random.choice('ABCD')}{random.randint(1, 40)}"
    boarding_group = random.choice(["A", "B", "C"])

    booking.status = "checked_in"
    await db.commit()

    flight_number = None
    origin = None
    destination = None
    departure_str = None
    arrival_str = None
    boarding_time_str = None
    travel_date_str = None
    aircraft = None

    if flight:
        from .flights import project_flight_to_date
        flight_number = flight.flight_number
        origin = flight.origin
        destination = flight.destination
        aircraft = flight.aircraft
        travel_date_str = booking.travel_date.isoformat() if booking.travel_date else None

        if booking.travel_date:
            dep, arr = project_flight_to_date(flight, booking.travel_date)
        else:
            dep = flight.departure
            arr = flight.arrival
        departure_str = dep.isoformat()
        arrival_str = arr.isoformat()
        boarding_time_str = (dep - timedelta(minutes=30)).isoformat()

    return BoardingPass(
        booking_id=str(booking.id),
        pnr=booking.pnr,
        passenger_name=booking.passenger_name,
        seat=seat,
        gate=gate,
        boarding_group=boarding_group,
        boarding_pass_url=f"https://autopilotairlines.com/pass/{booking.pnr}/{seat}",
        flight_number=flight_number,
        origin=origin,
        destination=destination,
        departure=departure_str,
        arrival=arrival_str,
        boarding_time=boarding_time_str,
        travel_date=travel_date_str,
        aircraft=aircraft,
        cabin_class=booking.cabin_class or "economy",
    )


class UndoCheckInRequest(BaseModel):
    booking_id: str


@router.post("/undo")
async def undo_check_in(
    body: UndoCheckInRequest,
    current_user: dict | None = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Booking).where(Booking.id == uuid.UUID(body.booking_id))
    )
    booking = result.scalar_one_or_none()
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")
    if booking.status != "checked_in":
        raise HTTPException(status_code=400, detail="Booking is not checked in")

    booking.status = "confirmed"
    await db.commit()

    return {"status": "confirmed", "pnr": booking.pnr}


@router.get("/status/{pnr}")
async def check_in_status(pnr: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Booking).where(Booking.pnr == pnr))
    booking = result.scalar_one_or_none()
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")
    return {
        "pnr": booking.pnr,
        "status": booking.status,
        "passenger_name": booking.passenger_name,
        "passenger_email": booking.passenger_email,
    }
