"""Data providers. Each returns a validated SensorReadingIn; failures are isolated per station."""
import logging
import math
import random
from datetime import datetime, timezone
from typing import Protocol

import httpx

from app.core.config import Settings
from app.schemas.sensor import SensorReadingIn, Station
from app.services.aqi import compute_aqi

log = logging.getLogger(__name__)


class Provider(Protocol):
    name: str

    async def fetch(self, client: httpx.AsyncClient, station: Station) -> SensorReadingIn | None: ...


class OpenWeatherProvider:
    name = "openweathermap"
    BASE = "https://api.openweathermap.org/data/2.5"

    def __init__(self, api_key: str) -> None:
        self.api_key = api_key

    async def fetch(self, client: httpx.AsyncClient, station: Station) -> SensorReadingIn | None:
        params = {"lat": station.lat, "lon": station.lon, "appid": self.api_key}
        pol = (await client.get(f"{self.BASE}/air_pollution", params=params)).raise_for_status().json()
        wx = (await client.get(f"{self.BASE}/weather", params={**params, "units": "metric"})).raise_for_status().json()
        item = pol["list"][0]
        comp = item["components"]
        pm25, pm10 = comp.get("pm2_5"), comp.get("pm10")
        return SensorReadingIn(
            station_id=station.id, city=station.city, latitude=station.lat, longitude=station.lon,
            time=datetime.fromtimestamp(item["dt"], tz=timezone.utc),
            pm25=pm25, pm10=pm10, no2=comp.get("no2"), co=comp.get("co"),
            aqi=compute_aqi(pm25, pm10),
            temperature=wx.get("main", {}).get("temp"), humidity=wx.get("main", {}).get("humidity"),
            source=self.name, raw={"air_pollution": item, "weather_main": wx.get("main")},
        )


class CPCBProvider:
    """Best-effort data.gov.in realtime AQI feed (needs a free API key). The resource id and field
    names are the commonly published ones - verify on data.gov.in if the feed changes."""

    name = "cpcb"
    URL = "https://api.data.gov.in/resource/3b01bcb8-0b14-4abf-b6f2-c1bfd384ba69"

    def __init__(self, api_key: str) -> None:
        self.api_key = api_key

    async def fetch(self, client: httpx.AsyncClient, station: Station) -> SensorReadingIn | None:
        params = {"api-key": self.api_key, "format": "json", "limit": 200, "filters[city]": station.city}
        rows = (await client.get(self.URL, params=params)).raise_for_status().json().get("records", [])
        if not rows:
            return None
        vals: dict[str, float] = {}
        for r in rows:
            try:
                vals.setdefault(r["pollutant_id"], float(r["pollutant_avg"]))
            except (KeyError, TypeError, ValueError):
                continue
        pm25, pm10 = vals.get("PM2.5"), vals.get("PM10")
        return SensorReadingIn(
            station_id=f"cpcb-{station.id}", city=station.city, latitude=station.lat, longitude=station.lon,
            time=datetime.now(timezone.utc), pm25=pm25, pm10=pm10, no2=vals.get("NO2"),
            co=(vals["CO"] * 1000 if "CO" in vals else None),  # mg/m3 -> ug/m3
            aqi=compute_aqi(pm25, pm10), source=self.name, raw={"pollutants": vals},
        )


class SimulatedProvider:
    """Dev fallback when no API keys are set. Rows are tagged source='simulated'."""

    name = "simulated"

    async def fetch(self, client: httpx.AsyncClient, station: Station) -> SensorReadingIn | None:
        now = datetime.now(timezone.utc)
        h = now.hour + now.minute / 60
        rush = math.exp(-((h - 9) ** 2) / 6) + math.exp(-((h - 19) ** 2) / 6)
        pm25 = max(5.0, 45 + 40 * rush + random.gauss(0, 6))
        pm10 = pm25 * random.uniform(1.4, 1.9)
        return SensorReadingIn(
            station_id=station.id, city=station.city, latitude=station.lat, longitude=station.lon,
            time=now, pm25=round(pm25, 1), pm10=round(pm10, 1),
            no2=round(20 + 25 * rush + random.gauss(0, 3), 1), co=round(400 + 500 * rush + random.gauss(0, 40), 1),
            temperature=round(28 + 6 * math.sin((h - 9) / 24 * 2 * math.pi) + random.gauss(0, 0.4), 1),
            humidity=round(55 - 15 * math.sin((h - 9) / 24 * 2 * math.pi), 1),
            aqi=compute_aqi(pm25, pm10), source=self.name,
        )


def build_providers(settings: Settings) -> list[Provider]:
    providers: list[Provider] = []
    if settings.openweather_api_key:
        providers.append(OpenWeatherProvider(settings.openweather_api_key))
    if settings.cpcb_api_key:
        providers.append(CPCBProvider(settings.cpcb_api_key))
    return providers or [SimulatedProvider()]
