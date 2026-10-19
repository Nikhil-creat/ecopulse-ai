#!/usr/bin/env python3
"""Backfill N days of hourly SIMULATED readings so forecasting/drift/dashboard work immediately in dev.
Rows are tagged source='simulated-backfill'. Usage:
  python3 scripts/backfill_simulated.py [--base http://localhost] [--days 14] [--api-key KEY]
"""
import argparse
import json
import math
import random
import urllib.request
from datetime import datetime, timedelta, timezone

STATIONS = [("warangal-01", "Warangal", 17.9689, 79.5941), ("hyderabad-01", "Hyderabad", 17.385, 78.4867),
            ("delhi-01", "Delhi", 28.6139, 77.2090)]
BASE_PM25 = {"warangal-01": 45, "hyderabad-01": 60, "delhi-01": 110}


def aqi_pm25(v: float) -> float:
    table = [(30, 0, 50), (60, 51, 100), (90, 101, 200), (120, 201, 300), (250, 301, 400), (380, 401, 500)]
    lo_c = 0
    for hi_c, lo_i, hi_i in table:
        if v <= hi_c:
            return round(lo_i + (v - lo_c) * (hi_i - lo_i) / (hi_c - lo_c), 1)
        lo_c = hi_c
    return 500.0


def post(url: str, payload: dict, key: str | None) -> dict:
    req = urllib.request.Request(url, json.dumps(payload).encode(), {"Content-Type": "application/json"})
    if key:
        req.add_header("X-API-Key", key)
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://localhost")
    ap.add_argument("--days", type=int, default=14)
    ap.add_argument("--api-key")
    a = ap.parse_args()
    now = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
    rows = []
    for sid, city, lat, lon in STATIONS:
        for h in range(a.days * 24, 0, -1):
            t = now - timedelta(hours=h)
            hour = t.hour
            rush = math.exp(-((hour - 9) ** 2) / 6) + math.exp(-((hour - 19) ** 2) / 6)
            pm25 = max(5.0, BASE_PM25[sid] * (0.8 + 0.5 * rush) + random.gauss(0, 5))
            pm10 = pm25 * random.uniform(1.4, 1.9)
            rows.append({"station_id": sid, "city": city, "latitude": lat, "longitude": lon, "time": t.isoformat(),
                         "pm25": round(pm25, 1), "pm10": round(pm10, 1), "no2": round(20 + 25 * rush + random.gauss(0, 3), 1),
                         "co": round(400 + 500 * rush + random.gauss(0, 40), 1),
                         "temperature": round(28 + 6 * math.sin((hour - 9) / 24 * 2 * math.pi) + random.gauss(0, 0.4), 1),
                         "humidity": round(55 - 15 * math.sin((hour - 9) / 24 * 2 * math.pi), 1),
                         "aqi": aqi_pm25(pm25), "source": "simulated-backfill"})
    for i in range(0, len(rows), 500):
        print(post(f"{a.base}/api/v1/ingest/readings", {"readings": rows[i : i + 500]}, a.api_key))
    print(f"backfilled {len(rows)} rows")


if __name__ == "__main__":
    main()
