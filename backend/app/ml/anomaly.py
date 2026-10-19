import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest

FEATURES = ["pm25", "pm10", "no2", "co", "temperature", "humidity"]


def detect(df: pd.DataFrame, recent_hours: int = 48, contamination: float = 0.02) -> list[dict]:
    """Isolation Forest over multivariate hourly features, trained on history before the recent window.
    Each flagged hour reports the feature that deviates most (robust z-score vs history)."""
    cols = [c for c in FEATURES if c in df and df[c].notna().sum() > 24]
    d = df[cols].ffill(limit=3).dropna()
    if len(d) < recent_hours + 48 or len(cols) < 2:
        return []
    hist, recent = d.iloc[:-recent_hours], d.iloc[-recent_hours:]
    med, mad = hist.median(), (hist - hist.median()).abs().median() * 1.4826
    mad = mad.replace(0, 1.0)

    def feats(x: pd.DataFrame) -> np.ndarray:
        z = ((x - med) / mad).to_numpy()
        hr = x.index.hour.to_numpy()
        return np.column_stack([z, np.sin(2 * np.pi * hr / 24), np.cos(2 * np.pi * hr / 24)])

    model = IsolationForest(n_estimators=200, contamination=contamination, random_state=0).fit(feats(hist))
    pred, score = model.predict(feats(recent)), model.score_samples(feats(recent))
    z_recent = (recent - med) / mad
    out = []
    for i in np.where(pred == -1)[0]:
        top = z_recent.iloc[i].abs().idxmax()
        out.append({"time": recent.index[i].isoformat(), "score": round(float(score[i]), 3), "top_feature": top,
                    "robust_z": round(float(z_recent.iloc[i][top]), 1), "value": round(float(recent.iloc[i][top]), 2)})
    return sorted(out, key=lambda r: r["score"])
