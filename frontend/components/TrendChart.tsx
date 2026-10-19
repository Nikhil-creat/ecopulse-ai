"use client";
import { useEffect, useMemo, useState } from "react";
import { Area, CartesianGrid, ComposedChart, Line, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { ForecastSummary, SeriesPoint, getJSON } from "@/lib/api";

const FIELDS = ["pm25", "pm10", "no2", "aqi", "temperature"] as const;
type Field = (typeof FIELDS)[number];
type Row = { t: number; value?: number; forecast?: number; range?: [number, number] };

export default function TrendChart({ stationId }: { stationId: string | null }) {
  const [field, setField] = useState<Field>("pm25");
  const [series, setSeries] = useState<SeriesPoint[]>([]);
  const [fc, setFc] = useState<ForecastSummary | null>(null);
  const [note, setNote] = useState("");

  useEffect(() => {
    if (!stationId) return;
    let alive = true;
    setNote("");
    getJSON<{ points: SeriesPoint[] }>(`/stats/timeseries?station_id=${encodeURIComponent(stationId)}&field=${field}&hours=48`)
      .then((d) => alive && setSeries(d.points))
      .catch(() => alive && setSeries([]));
    getJSON<ForecastSummary>(`/forecasts?station_id=${encodeURIComponent(stationId)}&pollutant=${field}`)
      .then((d) => alive && setFc(d))
      .catch(() => {
        if (alive) {
          setFc(null);
          setNote("Forecast needs ~12 hourly points of history.");
        }
      });
    return () => {
      alive = false;
    };
  }, [stationId, field]);

  const rows = useMemo<Row[]>(() => {
    const hist: Row[] = series.map((p) => ({ t: new Date(p.time).getTime(), value: p.value }));
    if (!hist.length || !fc) return hist;
    const last = hist[hist.length - 1];
    last.forecast = last.value;
    const fut: Row[] = fc.points.map((p) => ({
      t: last.t + p.horizon_hours * 3600_000,
      forecast: p.predicted,
      range: [p.lower, p.upper],
    }));
    return [...hist, ...fut];
  }, [series, fc]);

  return (
    <div className="rounded-2xl border border-slate-800 bg-slate-900/60 p-4">
      <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
        <p className="text-sm font-semibold">History &amp; forecast</p>
        <div className="flex gap-1">
          {FIELDS.map((f) => (
            <button key={f} onClick={() => setField(f)}
              className={`rounded-md px-2 py-1 text-xs ${f === field ? "bg-emerald-500 text-slate-950" : "bg-slate-800 text-slate-300"}`}>
              {f.toUpperCase()}
            </button>
          ))}
        </div>
      </div>
      <div className="h-64">
        <ResponsiveContainer>
          <ComposedChart data={rows}>
            <CartesianGrid stroke="#1e293b" />
            <XAxis dataKey="t" type="number" scale="time" domain={["dataMin", "dataMax"]} stroke="#64748b" fontSize={11}
              tickFormatter={(t: number) => new Date(t).toLocaleString([], { weekday: "short", hour: "2-digit" })} />
            <YAxis stroke="#64748b" fontSize={11} width={40} />
            <Tooltip contentStyle={{ background: "#0f172a", border: "1px solid #334155" }}
              labelFormatter={(t: number) => new Date(t).toLocaleString()} />
            <Area dataKey="range" stroke="none" fill="#38bdf8" fillOpacity={0.18} isAnimationActive={false} />
            <Line dataKey="value" stroke="#34d399" dot={false} strokeWidth={2} isAnimationActive={false} />
            <Line dataKey="forecast" stroke="#38bdf8" strokeDasharray="5 4" dot={false} strokeWidth={2} isAnimationActive={false} />
          </ComposedChart>
        </ResponsiveContainer>
      </div>
      <p className="mt-1 text-xs text-slate-500">
        {fc ? `Forecast model: ${fc.model}${fc.model.startsWith("baseline") ? " (simple trend baseline, not a trained model)" : ""}` : note}
      </p>
    </div>
  );
}
