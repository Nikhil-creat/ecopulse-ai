from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Float, SmallInteger, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class SensorReading(Base):
    """TimescaleDB hypertable partitioned on `time`."""

    __tablename__ = "sensor_readings"

    station_id: Mapped[str] = mapped_column(Text, primary_key=True)
    time: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True)
    city: Mapped[str | None] = mapped_column(Text)
    latitude: Mapped[float | None] = mapped_column(Float)
    longitude: Mapped[float | None] = mapped_column(Float)
    aqi: Mapped[float | None] = mapped_column(Float)
    pm25: Mapped[float | None] = mapped_column(Float)
    pm10: Mapped[float | None] = mapped_column(Float)
    no2: Mapped[float | None] = mapped_column(Float)
    co: Mapped[float | None] = mapped_column(Float)
    temperature: Mapped[float | None] = mapped_column(Float)
    humidity: Mapped[float | None] = mapped_column(Float)
    source: Mapped[str] = mapped_column(Text, server_default="unknown")
    quality_flag: Mapped[int] = mapped_column(SmallInteger, server_default=text("0"))
    raw: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
