"""Hourly time-series forecaster (no app imports -> unit-testable).

Candidates are scored on a 24 h hold-out and the best is refit on all data:
  holt-winters-24  : damped additive trend + additive daily seasonality (needs >= 72 h)
  damped-trend     : damped additive trend, no seasonality
  seasonal-naive   : value from 24 h earlier (needs >= 48 h)
"""
import warnings
from dataclasses import dataclass

import numpy as np
import pandas as pd
from statsmodels.tsa.holtwinters import ExponentialSmoothing

HORIZON = 72
REPORT_HORIZONS = (6, 12, 24, 48, 72)


@dataclass
class ForecastResult:
    model: str
    preds: np.ndarray        # length HORIZON, index 0 = +1 h
    resid_std: float
    holdout_mae: float | None
    n_train: int


def regularise(times: list, values: list[float]) -> pd.Series:
    s = pd.Series(values, index=pd.DatetimeIndex(times)).sort_index()
    s = s[~s.index.duplicated()]
    full = pd.date_range(s.index.min().floor("h"), s.index.max().floor("h"), freq="h")
    return s.reindex(full).interpolate(limit=6).dropna()


def _fit_predict(name: str, y: np.ndarray, steps: int) -> np.ndarray:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        if name == "holt-winters-24":
            m = ExponentialSmoothing(y, trend="add", damped_trend=True, seasonal="add", seasonal_periods=24,
                                     initialization_method="estimated").fit()
            return np.asarray(m.forecast(steps))
        if name == "damped-trend":
            m = ExponentialSmoothing(y, trend="add", damped_trend=True, initialization_method="estimated").fit()
            return np.asarray(m.forecast(steps))
        reps = int(np.ceil(steps / 24))
        return np.tile(y[-24:], reps)[:steps]


def forecast_series(series: pd.Series, non_negative: bool = True) -> ForecastResult | None:
    y = series.to_numpy(dtype=float)
    n = len(y)
    if n < 24:
        return None
    candidates = ["damped-trend"] + (["seasonal-naive"] if n >= 48 else []) + (["holt-winters-24"] if n >= 72 else [])
    maes: dict[str, float] = {}
    best, holdout_errs = candidates[0], None
    if n >= 72:
        train, test = y[:-24], y[-24:]
        for c in candidates:
            try:
                pred = _fit_predict(c, train, 24)
                maes[c] = float(np.mean(np.abs(pred - test)))
                if maes[c] <= maes.get(best, np.inf):
                    best = c
            except Exception:  # noqa: BLE001 - a failing candidate is simply skipped
                continue
        if best in maes:
            holdout_errs = _fit_predict(best, train, 24) - test
    try:
        preds = _fit_predict(best, y, HORIZON)
    except Exception:  # noqa: BLE001
        best, preds = "seasonal-naive" if n >= 24 else "damped-trend", _fit_predict("seasonal-naive", y, HORIZON)
    if non_negative:
        preds = np.clip(preds, 0, None)
    std = float(np.std(holdout_errs)) if holdout_errs is not None else float(np.std(np.diff(y))) or 1.0
    return ForecastResult(best, preds, max(std, 1e-6), maes.get(best), n)


def bounds(res: ForecastResult, horizon: int, z: float = 1.28) -> tuple[float, float, float]:
    pred = float(res.preds[horizon - 1])
    band = z * res.resid_std * np.sqrt(1 + horizon / 24)
    return pred, max(0.0, pred - band), pred + band
