from celery import Celery
from celery.schedules import crontab

from app.core.config import get_settings

settings = get_settings()

celery = Celery("ecopulse", broker=settings.redis_url, backend=settings.redis_url, include=["app.workers.tasks"])
celery.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    worker_prefetch_multiplier=1,
    beat_schedule={
        "heartbeat": {"task": "app.workers.tasks.heartbeat", "schedule": 300.0},
        "fetch-sensor-data": {"task": "app.workers.tasks.fetch_sensor_data",
                              "schedule": float(settings.ingest_interval_seconds)},
        "train-forecasts": {"task": "app.workers.tasks.train_forecasts", "schedule": crontab(minute=20, hour="*/3")},
        "backtest-daily": {"task": "app.workers.tasks.run_backtest_task", "schedule": crontab(hour=3, minute=30)},
        "drift-monitor": {"task": "app.workers.tasks.drift_monitor", "schedule": crontab(minute=5)},
    },
)
