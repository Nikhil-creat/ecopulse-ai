"""Optional MLflow tracking. No-op unless MLFLOW_TRACKING_URI is set; never raises into callers."""
import logging
import os
from contextlib import contextmanager
from typing import Any

log = logging.getLogger(__name__)


class _Noop:
    def params(self, p: dict[str, Any]) -> None: ...
    def metrics(self, m: dict[str, float], step: int | None = None) -> None: ...
    def artifact(self, path: str) -> None: ...


class _Live(_Noop):
    def __init__(self, mlflow: Any) -> None:
        self.m = mlflow

    def _safe(self, fn: Any, *a: Any, **k: Any) -> None:
        try:
            fn(*a, **k)
        except Exception as exc:  # noqa: BLE001
            log.warning("mlflow call failed: %r", exc)

    def params(self, p: dict[str, Any]) -> None:
        self._safe(self.m.log_params, {k: str(v)[:250] for k, v in p.items()})

    def metrics(self, m: dict[str, float], step: int | None = None) -> None:
        self._safe(self.m.log_metrics, {k: float(v) for k, v in m.items()}, step=step)

    def artifact(self, path: str) -> None:
        self._safe(self.m.log_artifact, path)


@contextmanager
def tracked_run(experiment: str, run_name: str):
    uri = os.getenv("MLFLOW_TRACKING_URI")
    if not uri:
        yield _Noop()
        return
    try:
        import mlflow

        mlflow.set_tracking_uri(uri)
        mlflow.set_experiment(experiment)
        mlflow.start_run(run_name=run_name)
    except Exception as exc:  # noqa: BLE001
        log.warning("mlflow unavailable (%r); continuing untracked", exc)
        yield _Noop()
        return
    try:
        yield _Live(mlflow)
    finally:
        try:
            mlflow.end_run()
        except Exception:  # noqa: BLE001
            pass
