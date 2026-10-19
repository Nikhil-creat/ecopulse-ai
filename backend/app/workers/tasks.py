import logging
import uuid
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

from app.core.config import get_settings
from app.db.worker_session import run_async, worker_session
from app.workers.celery_app import celery

log = logging.getLogger(__name__)
_analyzer = None  # lazy singleton: torch is only imported inside the worker


@celery.task(name="app.workers.tasks.heartbeat")
def heartbeat() -> str:
    return datetime.now(timezone.utc).isoformat()


@celery.task(name="app.workers.tasks.fetch_sensor_data", autoretry_for=(httpx.HTTPError,),
             retry_backoff=True, max_retries=3)
def fetch_sensor_data() -> dict[str, Any]:
    from app.services.ingestion import fetch_live, store_readings

    async def _run() -> dict[str, Any]:
        readings = await fetch_live(get_settings())
        if not readings:
            return {"received": 0, "stored": 0, "suspect": 0, "failed": 0}
        async with worker_session() as session:
            return (await store_readings(session, readings)).model_dump()

    result = run_async(_run())
    log.info("ingest result: %s", result)
    return result


@celery.task(name="app.workers.tasks.run_cnn_analysis")
def run_cnn_analysis(image_path: str, region: str, image_type: str = "satellite",
                     bbox: list[float] | None = None, captured_at: str | None = None) -> dict[str, Any]:
    global _analyzer
    from PIL import Image

    from app.ml.spatial_cnn import SpatialAnalyzer
    from app.models import SatelliteAnalysis

    settings = get_settings()
    if _analyzer is None:
        _analyzer = SpatialAnalyzer(Path(settings.artifacts_dir) / "models" / "spatial_cnn.pt")
    with Image.open(image_path) as img:
        res = _analyzer.analyze(img)

    row_id = uuid.uuid4()
    ts = datetime.fromisoformat(captured_at) if captured_at else datetime.now(timezone.utc)

    async def _save() -> None:
        async with worker_session() as session:
            session.add(SatelliteAnalysis(
                captured_at=ts, id=row_id, region=region, bbox=bbox, image_uri=image_path,
                image_type=image_type, smog_severity_index=res.smog_severity_index,
                green_canopy_density=res.green_canopy_density, model_version=res.model_version,
                heatmap=res.heatmap, meta={"model_source": res.model_source},
            ))
            await session.commit()

    run_async(_save())
    return {"id": str(row_id), **{k: v for k, v in asdict(res).items() if k != "heatmap"}}


@celery.task(name="app.workers.tasks.drift_monitor")
def drift_monitor() -> dict[str, Any]:
    from dataclasses import asdict as _asdict

    from app.services.drift import run_drift_check

    async def _run() -> dict[str, Any]:
        async with worker_session() as session:
            return _asdict(await run_drift_check(session, get_settings()))

    report = run_async(_run())
    if report["retrain_recommended"]:
        retrain_models.delay(reason="drift", report_generated_at=report["generated_at"])
    return {"status": report["status"], "retrain_recommended": report["retrain_recommended"]}


@celery.task(name="app.workers.tasks.train_forecasts")
def train_forecasts() -> dict[str, Any]:
    from app.services.forecasting import train_and_forecast

    async def _run() -> dict[str, Any]:
        async with worker_session() as session:
            return await train_and_forecast(session)

    result = run_async(_run())
    log.info("forecast training: %s", result)
    return result


@celery.task(name="app.workers.tasks.retrain_models")
def retrain_models(reason: str, report_generated_at: str | None = None) -> dict[str, Any]:
    """Triggered by the drift monitor: refit every forecaster on fresh data."""
    log.warning("retrain requested (reason=%s, report=%s)", reason, report_generated_at)
    return train_forecasts()
