export const API = process.env.NEXT_PUBLIC_API_BASE ?? "/api/v1";

export type Reading = {
  station_id: string;
  time: string;
  city: string | null;
  latitude: number | null;
  longitude: number | null;
  aqi: number | null;
  pm25: number | null;
  pm10: number | null;
  no2: number | null;
  co: number | null;
  temperature: number | null;
  humidity: number | null;
  source: string;
  quality_flag: number;
};

export type HeatmapData = { grid: number; smog: number[][]; canopy: number[][] };
export type SatelliteAnalysis = {
  id: string;
  captured_at: string;
  region: string;
  smog_severity_index: number;
  green_canopy_density: number;
  model_version: string;
  heatmap: HeatmapData | null;
};
export type SeriesPoint = { time: string; value: number };
export type ForecastPoint = { horizon_hours: number; predicted: number; lower: number; upper: number };
export type ForecastSummary = { station_id: string; pollutant: string; model: string; points: ForecastPoint[]; peak_value: number };

export async function getJSON<T>(path: string): Promise<T> {
  const r = await fetch(`${API}${path}`, { cache: "no-store" });
  if (!r.ok) throw new Error(`${r.status} ${path}`);
  return (await r.json()) as T;
}

// CPCB National AQI bands
export const AQI_BANDS = [
  { max: 50, label: "Good", color: "#00b050" },
  { max: 100, label: "Satisfactory", color: "#92d050" },
  { max: 200, label: "Moderate", color: "#f5d300" },
  { max: 300, label: "Poor", color: "#ff9900" },
  { max: 400, label: "Very Poor", color: "#e53935" },
  { max: 500, label: "Severe", color: "#8b0000" },
] as const;

export function aqiBand(aqi: number | null | undefined) {
  if (aqi == null) return { label: "No data", color: "#64748b" };
  return AQI_BANDS.find((b) => aqi <= b.max) ?? AQI_BANDS[AQI_BANDS.length - 1];
}

export const WHO_24H: Record<string, number> = { pm25: 15, pm10: 45, no2: 25, co: 4000 };

export function hexToRgb(hex: string): [number, number, number] {
  const n = parseInt(hex.slice(1), 16);
  return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
}
