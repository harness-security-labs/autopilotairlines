import uuid
from datetime import datetime

from sqlalchemy import String, DateTime, Text, JSON, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from ..database import Base


class MCPServer(Base):
    __tablename__ = "mcp_servers"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255))
    url: Mapped[str] = mapped_column(String(500))
    auth_config: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    capabilities: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    schema_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class MCPTool(Base):
    __tablename__ = "mcp_tools"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), index=True)
    description: Mapped[str] = mapped_column(Text)
    server_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    input_schema: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    auth_type: Mapped[str] = mapped_column(String(50), default="none")
    status: Mapped[str] = mapped_column(String(20), default="active")
    schema_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
