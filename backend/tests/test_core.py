from datetime import datetime, timedelta, timezone

import numpy as np
import pytest

from app.services.aqi import aqi_category, compute_aqi
from app.services.rag.chunking import chunk_text


def test_aqi_breakpoints():
    assert compute_aqi(75, 120) == 150.5
    assert compute_aqi(None, None) is None
    assert aqi_category(250) == "Poor"
    assert aqi_category(450) == "Severe"


def test_chunking_respects_size_and_overlaps():
    text = "\n\n".join(f"Sentence number {i} about air quality and health effects." * 3 for i in range(40))
    chunks = chunk_text(text, max_chars=500, overlap=80)
    assert len(chunks) > 3
    assert all(len(c) <= 500 + 80 + 10 for c in chunks)
    assert chunks[1][:30] in chunks[0]  # overlap carried into next chunk


def test_drift_detects_shift_not_noise():
    from app.services.drift import compare

    rng = np.random.default_rng(0)
    ref = rng.normal(60, 10, 500)
    assert not compare("pm25", ref, rng.normal(60, 10, 100), 0.01, 0.25).drifted
    assert compare("pm25", ref, rng.normal(90, 10, 100), 0.01, 0.25).drifted


def test_forecaster_seasonal_signal():
    from app.ml.forecaster import bounds, forecast_series, regularise

    idx = [datetime(2026, 1, 1, tzinfo=timezone.utc) + timedelta(hours=h) for h in range(24 * 7)]
    vals = [50 + 20 * np.sin(2 * np.pi * h / 24) for h in range(24 * 7)]
    res = forecast_series(regularise(idx, vals))
    assert res is not None and len(res.preds) == 72
    pred, lo, hi = bounds(res, 24)
    assert lo <= pred <= hi and pred >= 0
    assert res.holdout_mae is not None and res.holdout_mae < 10


def test_forecaster_needs_history():
    from app.ml.forecaster import forecast_series, regularise

    idx = [datetime(2026, 1, 1, tzinfo=timezone.utc) + timedelta(hours=h) for h in range(10)]
    assert forecast_series(regularise(idx, [1.0] * 10)) is None


def _reading(**kw):
    from app.schemas.sensor import ReadingOut

    base = dict(station_id="s1", time=datetime.now(timezone.utc), city="X", latitude=1.0, longitude=1.0, aqi=100,
                pm25=50.0, pm10=80.0, no2=20.0, co=300.0, temperature=30.0, humidity=50.0, source="t", quality_flag=0)
    return ReadingOut(**{**base, **kw})


def test_integrity_flags_bad_data():
    pytest.importorskip("langchain_core")
    from app.agents.nodes import check_station

    assert check_station(_reading(), [], None).trusted
    assert not check_station(_reading(quality_flag=2), [], None).trusted
    stale = check_station(_reading(time=datetime.now(timezone.utc) - timedelta(hours=5)), [], None)
    assert any("stale" in i for i in stale.issues)
    flat = [_reading(pm25=40.0, time=datetime.now(timezone.utc) - timedelta(minutes=15 * i)) for i in range(9)]
    assert any("flatline" in i for i in check_station(_reading(pm25=40.0), flat, None).issues)


def test_policy_scales_with_level():
    pytest.importorskip("langchain_core")
    from app.agents.nodes import cross_check_cnn, plan_actions

    assert plan_actions("low", 10, 20, 10) == []
    assert len(plan_actions("severe", 300, 400, 90)) > len(plan_actions("high", 100, 150, 30))
    assert cross_check_cnn(250, 10, datetime.now(timezone.utc), "cnn").status == "discrepancy"
    assert cross_check_cnn(250, 80, datetime.now(timezone.utc), "cnn").status == "consistent"
