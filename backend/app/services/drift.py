"""MLOps drift monitor: compares a recent window against a reference window using the two-sample
KS test and the Wasserstein distance (normalised by the reference std)."""
import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
from scipy.stats import ks_2samp, wasserstein_distance
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.models import AuditLog, SensorReading

log = logging.getLogger(__name__)

FEATURES = ("aqi", "pm25", "pm10", "no2", "co", "temperature")


@dataclass
class FeatureDrift:
    feature: str
    n_reference: int
    n_current: int
    ks_stat: float
    ks_pvalue: float
    wasserstein_norm: float
    drifted: bool


@dataclass
class DriftReport:
    generated_at: str
    status: str  # ok | drift | insufficient_data
    retrain_recommended: bool
    features: list[FeatureDrift] = field(default_factory=list)
    windows: dict[str, str] = field(default_factory=dict)


def compare(feature: str, ref: np.ndarray, cur: np.ndarray, alpha: float, w_thr: float) -> FeatureDrift:
    ks = ks_2samp(ref, cur)
    scale = float(np.std(ref)) or 1e-9
    w = float(wasserstein_distance(ref, cur)) / scale
    return FeatureDrift(feature, len(ref), len(cur), float(ks.statistic), float(ks.pvalue), w,
                        bool(ks.pvalue < alpha and w > w_thr))


async def _column(session: AsyncSession, col, start: datetime, end: datetime) -> np.ndarray:
    stmt = select(col).where(SensorReading.time >= start, SensorReading.time < end,
                             SensorReading.quality_flag < 2, col.is_not(None))
    return np.asarray((await session.execute(stmt)).scalars().all(), dtype=float)


async def run_drift_check(session: AsyncSession, settings: Settings) -> DriftReport:
    now = datetime.now(timezone.utc)
    cur_start = now - timedelta(hours=settings.drift_current_hours)
    ref_start = cur_start - timedelta(days=settings.drift_reference_days)
    report = DriftReport(now.isoformat(), "ok", False,
                         windows={"reference": f"{ref_start.isoformat()} .. {cur_start.isoformat()}",
                                  "current": f"{cur_start.isoformat()} .. {now.isoformat()}"})
    for name in FEATURES:
        col = getattr(SensorReading, name)
        ref = await _column(session, col, ref_start, cur_start)
        cur = await _column(session, col, cur_start, now)
        if len(ref) < settings.drift_min_samples or len(cur) < settings.drift_min_samples:
            continue
        report.features.append(compare(name, ref, cur, settings.drift_ks_alpha,
                                       settings.drift_wasserstein_threshold))

    if not report.features:
        report.status = "insufficient_data"
    else:
        drifted = [f for f in report.features if f.drifted]
        report.retrain_recommended = len(drifted) >= 2
        report.status = "drift" if drifted else "ok"

    out = Path(settings.artifacts_dir) / "drift"
    out.mkdir(parents=True, exist_ok=True)
    (out / "latest.json").write_text(json.dumps(asdict(report), indent=2))
    session.add(AuditLog(actor="drift_monitor", actor_type="system", action="drift_check",
                         entity_type="model", details={"status": report.status,
                                                       "retrain_recommended": report.retrain_recommended}))
    await session.commit()
    return report
