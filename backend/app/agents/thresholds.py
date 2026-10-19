"""Guideline thresholds in ug/m3 (CO converted from mg/m3). Mirrors the seeded knowledge documents."""

WHO_2021_24H = {"pm25": 15.0, "pm10": 45.0, "no2": 25.0, "co": 4000.0}
CPCB_24H = {"pm25": 60.0, "pm10": 100.0, "no2": 80.0, "co": 2000.0}  # CO: 8-hour standard

CATEGORY_TO_LEVEL = {
    "Good": "low", "Satisfactory": "low", "Moderate": "moderate",
    "Poor": "high", "Very Poor": "very_high", "Severe": "severe",
}
LEVEL_ORDER = ["low", "moderate", "high", "very_high", "severe"]
