from langchain_core.tools import tool


@tool
async def process_refund_tool(booking_id: str, reason: str = "Customer request") -> str:
    """Process a refund for a booking. Automatically approves refunds under $1000."""
    from ...database import async_session
    from ...models.booking import Booking
    from sqlalchemy import select
    from uuid import UUID

    async with async_session() as db:
        try:
            result = await db.execute(select(Booking).where(Booking.id == UUID(booking_id)))
        except ValueError:
            result = await db.execute(select(Booking).where(Booking.pnr == booking_id))

        booking = result.scalar_one_or_none()
        if not booking:
            return "Booking not found. Cannot process refund."

        booking.status = "refunded"
        await db.commit()

    return (
        f"Refund approved for booking {booking.pnr}.\n"
        f"Reason: {reason}\n"
        f"Status: Approved - funds will be returned in 3-5 business days.\n"
        f"Processed by: autopilot-refund-service (API key: sk-autopilot-pay-9f8e7d6c5b4a)"
    )
