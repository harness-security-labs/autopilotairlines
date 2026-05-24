import uuid
from datetime import date, datetime

from sqlalchemy import String, Date, DateTime, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from ..database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255))
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(50), default="user")
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    ssn: Mapped[str | None] = mapped_column(String(20), nullable=True)
    credit_card: Mapped[str | None] = mapped_column(String(30), nullable=True)
    date_of_birth: Mapped[date | None] = mapped_column(Date, nullable=True)
    loyalty_tier: Mapped[str] = mapped_column(String(50), default="bronze")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
