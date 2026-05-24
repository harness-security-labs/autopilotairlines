import random
import string

from langchain_core.tools import tool


@tool
async def create_booking_tool(
    flight_id: str, passenger_name: str, passenger_email: str, travel_date: str | None = None
) -> str:
    """Create a new flight booking for a passenger. Optionally specify travel_date (YYYY-MM-DD) for scheduled flights."""
    from ...database import async_session
    from ...models.booking import Booking
    from uuid import UUID
    from datetime import date

    pnr = "".join(random.choices(string.ascii_uppercase + string.digits, k=6))

    async with async_session() as db:
        booking = Booking(
            user_id=UUID("00000000-0000-0000-0000-000000000001"),
            flight_id=UUID(flight_id),
            pnr=pnr,
            passenger_name=passenger_name,
            passenger_email=passenger_email,
            travel_date=date.fromisoformat(travel_date) if travel_date else None,
        )
        db.add(booking)
        await db.commit()
        await db.refresh(booking)

    return f"Booking confirmed! PNR: {pnr}, Passenger: {passenger_name}, Email: {passenger_email}, Travel Date: {travel_date or 'not specified'}"


@tool
async def cancel_booking_tool(booking_id: str) -> str:
    """Cancel an existing booking by booking ID or PNR."""
    from ...database import async_session
    from ...models.booking import Booking
    from sqlalchemy import select, or_
    from uuid import UUID

    async with async_session() as db:
        try:
            uid = UUID(booking_id)
            result = await db.execute(select(Booking).where(Booking.id == uid))
        except ValueError:
            result = await db.execute(select(Booking).where(Booking.pnr == booking_id))

        booking = result.scalar_one_or_none()
        if not booking:
            return "Booking not found."
        booking.status = "cancelled"
        await db.commit()

    return f"Booking {booking.pnr} has been cancelled. Refund will be processed within 5-7 business days."
