import uuid
from datetime import datetime, date

from sqlalchemy import String, DateTime, Date, Integer, Float, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from ..database import Base


class Flight(Base):
    __tablename__ = "flights"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    flight_number: Mapped[str] = mapped_column(String(20), index=True)
    origin: Mapped[str] = mapped_column(String(10))
    destination: Mapped[str] = mapped_column(String(10))
    departure: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    arrival: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    aircraft: Mapped[str] = mapped_column(String(50))
    status: Mapped[str] = mapped_column(String(20), default="scheduled")
    base_price: Mapped[float] = mapped_column(Float, default=199.0)
    available_seats: Mapped[int] = mapped_column(Integer, default=180)
    days_of_week: Mapped[str | None] = mapped_column(String(7), nullable=True)
    valid_from: Mapped[date | None] = mapped_column(Date, nullable=True)
    valid_until: Mapped[date | None] = mapped_column(Date, nullable=True)
    total_seats: Mapped[int] = mapped_column(Integer, default=180)
    economy_seats: Mapped[int] = mapped_column(Integer, default=0)
    premium_economy_seats: Mapped[int] = mapped_column(Integer, default=0)
    business_seats: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Seat(Base):
    __tablename__ = "seats"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    flight_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("flights.id"))
    seat_class: Mapped[str] = mapped_column(String(20))
    seat_number: Mapped[str] = mapped_column(String(10))
    status: Mapped[str] = mapped_column(String(20), default="available")
    price: Mapped[float] = mapped_column(Float)
