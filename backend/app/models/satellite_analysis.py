import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Float, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class SatelliteAnalysis(Base):
    """CNN metadata outputs. Hypertable on `captured_at`."""

    __tablename__ = "satellite_analyses"

    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True)
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    region: Mapped[str] = mapped_column(Text)
    bbox: Mapped[list[float] | None] = mapped_column(JSONB)
    image_uri: Mapped[str] = mapped_column(Text)
    image_type: Mapped[str] = mapped_column(Text, server_default="satellite")
    smog_severity_index: Mapped[float] = mapped_column(Float)
    green_canopy_density: Mapped[float] = mapped_column(Float)
    heat_island_intensity: Mapped[float | None] = mapped_column(Float)
    model_version: Mapped[str] = mapped_column(Text)
    heatmap: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    meta: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
