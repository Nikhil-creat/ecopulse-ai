from datetime import datetime, timedelta, timezone

import numpy as np
import pytest

pytest.importorskip("statsmodels")
pytest.importorskip("sklearn")
import pandas as pd  # noqa: E402

from app.ml import anomaly, forecaster  # noqa: E402


def _series(n=24 * 10, noise=2.0):
    idx = pd.date_range(datetime(2026, 1, 1, tzinfo=timezone.utc), periods=n, freq="h")
    rng = np.random.default_rng(1)
    return pd.Series(50 + 20 * np.sin(2 * np.pi * idx.hour / 24) + rng.normal(0, noise, n), index=idx)


def test_backtest_beats_persistence_on_seasonal_data():
    res = forecaster.backtest_series(_series())
    mae = {m: np.mean([e[0] for e in v]) for m, v in res.items()}
    assert min(mae, key=mae.get) != "persistence"


def test_explain_components_add_up():
    r = forecaster.explain(_series())
    c = r["components"]
    assert abs(sum(c.values()) - r["forecast"]) < 0.1 and "Forecast" in r["text"]


def test_anomaly_flags_injected_spike():
    s = _series(24 * 10)
    df = pd.DataFrame({"pm25": s, "pm10": s * 1.6, "no2": s * 0.4})
    df.iloc[-10, 0] += 400
    out = anomaly.detect(df)
    assert any(a["top_feature"] == "pm25" for a in out)
