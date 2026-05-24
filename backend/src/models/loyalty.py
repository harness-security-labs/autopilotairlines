import uuid
from datetime import datetime

from sqlalchemy import String, DateTime, Integer, Float, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from ..database import Base


class LoyaltyAccount(Base):
    __tablename__ = "loyalty_accounts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), unique=True)
    points: Mapped[int] = mapped_column(Integer, default=0)
    tier: Mapped[str] = mapped_column(String(50), default="bronze")
    tier_expiry: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class LoyaltyTransaction(Base):
    __tablename__ = "loyalty_transactions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    account_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("loyalty_accounts.id"))
    points: Mapped[int] = mapped_column(Integer)
    transaction_type: Mapped[str] = mapped_column(String(50))
    source: Mapped[str] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
