"use client";
import { useEffect, useMemo, useState } from "react";
import AqiGauge from "@/components/AqiGauge";
import AlertsPanel from "@/components/AlertsPanel";
import AuthBar from "@/components/AuthBar";
import ChatDrawer from "@/components/ChatDrawer";
import PollutantGrid from "@/components/PollutantGrid";
import ReportButton from "@/components/ReportButton";
import SystemStatus from "@/components/SystemStatus";
import SpatialMap from "@/components/SpatialMap";
import TrendChart from "@/components/TrendChart";
import { Reading, getJSON } from "@/lib/api";
import { useLiveMetrics } from "@/lib/useLiveMetrics";

const STATUS_STYLE = { live: "bg-emerald-400", connecting: "bg-amber-400", offline: "bg-red-500" } as const;

export default function Dashboard() {
  const [cities, setCities] = useState<string[]>([]);
  const [city, setCity] = useState<string | null>(null);
  const [station, setStation] = useState<string | null>(null);
  const [loadErr, setLoadErr] = useState(false);

  useEffect(() => {
    getJSON<Reading[]>("/readings/latest")
      .then((rs) => {
        const cs = Array.from(new Set(rs.map((r) => r.city).filter((c): c is string => !!c)));
        setCities(cs);
        setCity((c) => c ?? cs[0] ?? null);
      })
      .catch(() => setLoadErr(true));
  }, []);

  const { readings, status } = useLiveMetrics(city);
  const list = useMemo(() => Object.values(readings).filter((r) => r.quality_flag < 2), [readings]);
  const worst = useMemo(() => list.reduce<Reading | null>((a, r) => ((r.aqi ?? 0) > (a?.aqi ?? -1) ? r : a), null), [list]);
  const selected = (station && readings[station]) || worst;
  const meanAqi = useMemo(() => {
    const v = list.map((r) => r.aqi).filter((x): x is number => x != null);
    return v.length ? v.reduce((a, b) => a + b, 0) / v.length : null;
  }, [list]);
  const asOf = list.length ? new Date(Math.max(...list.map((r) => new Date(r.time).getTime()))) : null;

  return (
    <main className="mx-auto max-w-7xl space-y-4 p-4 md:p-6">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="neon text-3xl font-extrabold tracking-tight">EcoPulse AI</h1>
          <p className="text-xs text-slate-500">Autonomous Urban Climate Intelligence &amp; Decision Engine</p>
        </div>
        <div className="flex flex-wrap items-center gap-3">
          <select value={city ?? ""} onChange={(e) => { setCity(e.target.value); setStation(null); }}
            className="rounded-lg bg-slate-900 px-3 py-2 text-sm ring-1 ring-slate-800">
            {cities.length === 0 && <option value="">No data yet</option>}
            {cities.map((c) => <option key={c}>{c}</option>)}
          </select>
          <span className="flex items-center gap-2 text-xs text-slate-400">
            <span className={`h-2.5 w-2.5 rounded-full ${STATUS_STYLE[status]}`} />
            {status}{asOf ? ` · ${asOf.toLocaleTimeString()}` : ""}
          </span>
          <AuthBar />
          {city && <ReportButton city={city} />}
        </div>
      </header>

      <SystemStatus />

      {loadErr && <p className="rounded-lg bg-red-950 p-3 text-sm text-red-300">Could not reach the API. Is the stack running?</p>}
      {!city && !loadErr && (
        <p className="rounded-lg bg-slate-900 p-4 text-sm text-slate-400">
          No sensor data yet. Trigger ingestion with <code>POST /api/v1/ingest/fetch</code>, then refresh.
        </p>
      )}

      {city && (
        <>
          <section className="grid gap-4 md:grid-cols-3">
            <AqiGauge aqi={meanAqi} label={`${city} · mean AQI (${list.length} station${list.length === 1 ? "" : "s"})`} />
            <div className="space-y-2 md:col-span-2">
              <div className="flex flex-wrap items-center gap-2 text-sm">
                <span className="text-slate-400">Station:</span>
                {list.map((r) => (
                  <button key={r.station_id} onClick={() => setStation(r.station_id)}
                    className={`rounded-md px-2 py-1 text-xs ${selected?.station_id === r.station_id ? "bg-emerald-500 text-slate-950" : "bg-slate-800"}`}>
                    {r.station_id}
                  </button>
                ))}
                {selected?.source === "simulated" && <span className="rounded bg-amber-900 px-2 py-0.5 text-xs text-amber-300">simulated data</span>}
              </div>
              <PollutantGrid reading={selected ?? null} />
            </div>
          </section>
          <section className="grid gap-4 lg:grid-cols-2">
            <TrendChart stationId={selected?.station_id ?? null} />
            <SpatialMap city={city} readings={list} onSelect={setStation} />
          </section>
          <AlertsPanel city={city} />
        </>
      )}
      <ChatDrawer city={city} />
    </main>
  );
}
