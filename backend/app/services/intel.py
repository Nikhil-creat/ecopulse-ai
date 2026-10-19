import asyncio
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from sqlalchemy import func, literal_column, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.ml import anomaly, forecaster
from app.ml.tracking import tracked_run
from app.models import SensorReading

BACKTEST_POLLUTANTS = ("pm25", "pm10", "no2")


async def hourly(session: AsyncSession, station_id: str, field: str, days: int = 21) -> pd.Series:
    col = getattr(SensorReading, field)
    b = func.time_bucket(literal_column("interval '1 hour'"), SensorReading.time).label("b")
    since = datetime.now(timezone.utc) - timedelta(days=days)
    rows = (await session.execute(select(b, func.avg(col)).where(
        SensorReading.station_id == station_id, SensorReading.time >= since, SensorReading.quality_flag < 2,
        col.is_not(None)).group_by(b).order_by(b))).all()
    if len(rows) < 24:
        return pd.Series(dtype=float)
    return forecaster.regularise([r[0] for r in rows], [float(r[1]) for r in rows])


async def anomalies(session: AsyncSession, station_id: str) -> list[dict]:
    cols = {f: await hourly(session, station_id, f, 14) for f in anomaly.FEATURES}
    df = pd.DataFrame({k: v for k, v in cols.items() if len(v)})
    return await asyncio.to_thread(anomaly.detect, df) if not df.empty else []


async def run_backtest(session: AsyncSession) -> dict:
    stations = (await session.execute(select(SensorReading.station_id).where(
        SensorReading.time >= datetime.now(timezone.utc) - timedelta(days=21)).distinct())).scalars().all()
    agg: dict[str, dict[str, list[tuple[float, float]]]] = {p: {} for p in BACKTEST_POLLUTANTS}
    for sid in stations:
        for pol in BACKTEST_POLLUTANTS:
            s = await hourly(session, sid, pol)
            if len(s) < 96:
                continue
            res = await asyncio.to_thread(forecaster.backtest_series, s)
            for model, errs in res.items():
                agg[pol].setdefault(model, []).extend(errs)
    report: dict = {"generated_at": datetime.now(timezone.utc).isoformat(), "horizon_hours": 24, "pollutants": {}}
    for pol, models in agg.items():
        if not models:
            continue
        rows = {m: {"mae": round(float(np.mean([e[0] for e in v])), 2), "rmse": round(float(np.mean([e[1] for e in v])), 2),
                    "n": len(v)} for m, v in models.items()}
        base = rows.get("persistence", {}).get("mae")
        for m, r in rows.items():
            r["skill_vs_persistence"] = round(1 - r["mae"] / base, 3) if base else None
        report["pollutants"][pol] = {"best": min(rows, key=lambda m: rows[m]["mae"]), "models": rows}
    out = Path(get_settings().artifacts_dir) / "backtest"
    out.mkdir(parents=True, exist_ok=True)
    (out / "latest.json").write_text(json.dumps(report, indent=2))
    with tracked_run("forecast-backtest", f"backtest-{datetime.now(timezone.utc):%Y%m%d%H%M}") as t:
        t.params({"horizon_h": 24, "stations": len(stations)})
        for pol, info in report["pollutants"].items():
            t.metrics({f"{pol}_{m}_mae": r["mae"] for m, r in info["models"].items()})
        t.artifact(str(out / "latest.json"))
    return report
