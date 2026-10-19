"""CPCB (India NAQI) sub-index from PM2.5 / PM10 concentrations (ug/m3).
Only particulate sub-indices are used; the AQI is the max of the available sub-indices."""

_PM25 = [(0, 30, 0, 50), (30, 60, 51, 100), (60, 90, 101, 200),
         (90, 120, 201, 300), (120, 250, 301, 400), (250, 380, 401, 500)]
_PM10 = [(0, 50, 0, 50), (50, 100, 51, 100), (100, 250, 101, 200),
         (250, 350, 201, 300), (350, 430, 301, 400), (430, 510, 401, 500)]


def _sub_index(value: float, table: list[tuple[int, int, int, int]]) -> float:
    for c_lo, c_hi, i_lo, i_hi in table:
        if value <= c_hi:
            return i_lo + (value - c_lo) * (i_hi - i_lo) / (c_hi - c_lo)
    return 500.0


def compute_aqi(pm25: float | None, pm10: float | None) -> float | None:
    subs = []
    if pm25 is not None:
        subs.append(_sub_index(pm25, _PM25))
    if pm10 is not None:
        subs.append(_sub_index(pm10, _PM10))
    return round(max(subs), 1) if subs else None


def aqi_category(aqi: float) -> str:
    for limit, label in [(50, "Good"), (100, "Satisfactory"), (200, "Moderate"),
                         (300, "Poor"), (400, "Very Poor")]:
        if aqi <= limit:
            return label
    return "Severe"
