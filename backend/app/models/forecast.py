from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, Float, SmallInteger, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Forecast(Base):
    """Model outputs with confidence bounds. Hypertable on `issued_at`."""

    __tablename__ = "forecasts"

    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True)
    station_id: Mapped[str] = mapped_column(Text, primary_key=True)
    pollutant: Mapped[str] = mapped_column(Text, primary_key=True)
    horizon_hours: Mapped[int] = mapped_column(SmallInteger, primary_key=True)
    model_name: Mapped[str] = mapped_column(Text, primary_key=True)
    target_time: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    model_version: Mapped[str] = mapped_column(Text)
    predicted: Mapped[float] = mapped_column(Float)
    lower_bound: Mapped[float | None] = mapped_column(Float)
    upper_bound: Mapped[float | None] = mapped_column(Float)
    confidence_level: Mapped[float] = mapped_column(Float, server_default=text("0.95"))
    verified: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    meta: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
