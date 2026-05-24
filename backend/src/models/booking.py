import uuid
from datetime import datetime, date

from sqlalchemy import String, DateTime, Date, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from ..database import Base


class Booking(Base):
    __tablename__ = "bookings"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    flight_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("flights.id"))
    seat_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("seats.id"), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="confirmed")
    pnr: Mapped[str] = mapped_column(String(10), unique=True)
    passenger_name: Mapped[str] = mapped_column(String(255))
    passenger_email: Mapped[str] = mapped_column(String(255))
    cabin_class: Mapped[str] = mapped_column(String(20), default="economy")
    travel_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    coupon_code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Ticket(Base):
    __tablename__ = "tickets"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    booking_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("bookings.id"))
    passenger_name: Mapped[str] = mapped_column(String(255))
    seat: Mapped[str] = mapped_column(String(10))
    boarding_pass_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
