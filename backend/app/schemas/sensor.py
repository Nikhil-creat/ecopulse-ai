from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class Station(BaseModel):
    id: str
    city: str
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)


# Well-known city centres. Add exact station coordinates (e.g. Thorrur) via STATIONS_JSON.
DEFAULT_STATIONS: list[Station] = [
    Station(id="warangal-01", city="Warangal", lat=17.9689, lon=79.5941),
    Station(id="hyderabad-01", city="Hyderabad", lat=17.3850, lon=78.4867),
    Station(id="delhi-01", city="Delhi", lat=28.6139, lon=77.2090),
]


class SensorReadingIn(BaseModel):
    """Validated inbound reading. Units: ug/m3 for PM/NO2/CO, degC, % RH."""

    station_id: str = Field(min_length=1, max_length=64)
    time: datetime
    city: str | None = None
    latitude: float | None = Field(None, ge=-90, le=90)
    longitude: float | None = Field(None, ge=-180, le=180)
    aqi: float | None = Field(None, ge=0, le=1000)
    pm25: float | None = Field(None, ge=0, le=2000)
    pm10: float | None = Field(None, ge=0, le=3000)
    no2: float | None = Field(None, ge=0, le=3000)
    co: float | None = Field(None, ge=0, le=100_000)
    temperature: float | None = Field(None, ge=-90, le=70)
    humidity: float | None = Field(None, ge=0, le=100)
    source: str = "api"
    raw: dict[str, Any] | None = None

    @field_validator("time")
    @classmethod
    def _utc(cls, v: datetime) -> datetime:
        return (v.replace(tzinfo=timezone.utc) if v.tzinfo is None else v).astimezone(timezone.utc)


class IngestBatch(BaseModel):
    readings: list[SensorReadingIn] = Field(min_length=1, max_length=1000)


class IngestResult(BaseModel):
    received: int
    stored: int
    suspect: int
    failed: int


class ReadingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    station_id: str
    time: datetime
    city: str | None
    latitude: float | None
    longitude: float | None
    aqi: float | None
    pm25: float | None
    pm10: float | None
    no2: float | None
    co: float | None
    temperature: float | None
    humidity: float | None
    source: str
    quality_flag: int


class SatelliteOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    captured_at: datetime
    region: str
    image_type: str
    smog_severity_index: float
    green_canopy_density: float
    heat_island_intensity: float | None
    model_version: str
    heatmap: dict[str, Any] | None
