import asyncio
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, literal_column, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.ml.forecaster import REPORT_HORIZONS, bounds, forecast_series, regularise
from app.models import AuditLog, Forecast, SensorReading

log = logging.getLogger(__name__)
POLLUTANTS = ("pm25", "pm10", "no2", "aqi", "temperature")
HISTORY_DAYS = 14


async def train_and_forecast(session: AsyncSession) -> dict:
    now = datetime.now(timezone.utc)
    issued = now.replace(minute=0, second=0, microsecond=0)
    since = now - timedelta(days=HISTORY_DAYS)
    stations = (await session.execute(
        select(SensorReading.station_id).where(SensorReading.time >= since).distinct())).scalars().all()
    bucket = func.time_bucket(literal_column("interval '1 hour'"), SensorReading.time).label("b")
    written, skipped = 0, 0
    for sid in stations:
        for pol in POLLUTANTS:
            col = getattr(SensorReading, pol)
            rows = (await session.execute(
                select(bucket, func.avg(col)).where(SensorReading.station_id == sid, SensorReading.time >= since,
                                                    SensorReading.quality_flag < 2, col.is_not(None))
                .group_by(bucket).order_by(bucket))).all()
            if len(rows) < 24:
                skipped += 1
                continue
            series = regularise([r[0] for r in rows], [float(r[1]) for r in rows])
            res = await asyncio.to_thread(forecast_series, series, pol != "temperature")
            if res is None:
                skipped += 1
                continue
            vals = []
            for h in REPORT_HORIZONS:
                pred, lo, hi = bounds(res, h)
                vals.append(dict(
                    issued_at=issued, station_id=sid, pollutant=pol, horizon_hours=h, model_name=res.model,
                    target_time=issued + timedelta(hours=h), model_version=f"v1-{issued:%Y%m%d%H}",
                    predicted=round(pred, 2), lower_bound=round(lo, 2), upper_bound=round(hi, 2),
                    confidence_level=0.8, verified=False,
                    meta={"holdout_mae": res.holdout_mae, "n_train_hours": res.n_train}))
            stmt = insert(Forecast).values(vals)
            stmt = stmt.on_conflict_do_update(
                index_elements=["issued_at", "station_id", "pollutant", "horizon_hours", "model_name"],
                set_={c: stmt.excluded[c] for c in ("target_time", "model_version", "predicted", "lower_bound",
                                                    "upper_bound", "confidence_level", "meta")})
            await session.execute(stmt)
            written += len(vals)
    session.add(AuditLog(actor="forecaster", actor_type="system", action="train_forecasts",
                         details={"stations": len(stations), "rows": written, "skipped_series": skipped}))
    await session.commit()
    return {"stations": len(stations), "rows": written, "skipped_series": skipped}
