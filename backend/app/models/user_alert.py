import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, Text, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class UserAlert(Base):
    __tablename__ = "user_alerts"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    user_ref: Mapped[str] = mapped_column(Text)
    city: Mapped[str] = mapped_column(Text)
    pollutant: Mapped[str] = mapped_column(Text)
    threshold: Mapped[float] = mapped_column(Float)
    severity: Mapped[str] = mapped_column(Text, server_default="warning")
    message: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, server_default="active")
    channel: Mapped[str] = mapped_column(Text, server_default="dashboard")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    triggered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
