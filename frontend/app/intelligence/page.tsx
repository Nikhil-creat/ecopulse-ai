"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { Reading, getJSON } from "@/lib/api";

type ModelRow = { mae: number; rmse: number; n: number; skill_vs_persistence: number | null };
type Backtest = { generated_at: string; horizon_hours: number; pollutants: Record<string, { best: string; models: Record<string, ModelRow> }> };
type Anomaly = { time: string; score: number; top_feature: string; robust_z: number; value: number };
type Explain = { forecast: number; text: string; components: Record<string, number>; horizon_hours: number };

export default function Intelligence() {
  const [stations, setStations] = useState<string[]>([]);
  const [sid, setSid] = useState("");
  const [bt, setBt] = useState<Backtest | null>(null);
  const [btMsg, setBtMsg] = useState("");
  const [an, setAn] = useState<Anomaly[] | null>(null);
  const [ex, setEx] = useState<Explain | null>(null);
  const [exMsg, setExMsg] = useState("");

  useEffect(() => {
    getJSON<Reading[]>("/readings/latest").then((rs) => { const ids = rs.map((r) => r.station_id); setStations(ids); setSid(ids[0] ?? ""); }).catch(() => undefined);
    getJSON<Backtest>("/intel/backtest").then(setBt).catch(() => setBtMsg("No backtest yet. It needs about 4 days of hourly history; it then runs daily."));
  }, []);
  useEffect(() => {
    if (!sid) return;
    setAn(null); setEx(null); setExMsg("");
    getJSON<{ anomalies: Anomaly[] }>(`/intel/anomalies?station_id=${encodeURIComponent(sid)}`).then((d) => setAn(d.anomalies)).catch(() => setAn([]));
    getJSON<Explain>(`/intel/explain?station_id=${encodeURIComponent(sid)}&pollutant=pm25&horizon=24`).then(setEx).catch(() => setExMsg("Needs at least 72 hourly points."));
  }, [sid]);

  return (
    <main className="mx-auto max-w-5xl space-y-4 p-4 md:p-6">
      <header className="flex items-center justify-between">
        <h1 className="neon text-2xl font-extrabold">Model intelligence</h1>
        <Link href="/" className="glass-sm px-3 py-1.5 text-sm">← Dashboard</Link>
      </header>

      <section className="glass p-4">
        <p className="mb-1 text-sm font-semibold">Forecast accuracy (rolling back-test, +{bt?.horizon_hours ?? 24} h)</p>
        {bt ? Object.entries(bt.pollutants).map(([pol, info]) => (
          <div key={pol} className="mt-3 overflow-x-auto">
            <p className="text-xs text-slate-400">{pol.toUpperCase()} · best model: <b className="text-emerald-300">{info.best}</b></p>
            <table className="mt-1 w-full text-left text-sm">
              <thead className="text-xs text-slate-500"><tr><th>Model</th><th>MAE</th><th>RMSE</th><th>Skill vs persistence</th><th>Tests</th></tr></thead>
              <tbody>{Object.entries(info.models).map(([m, r]) => (
                <tr key={m} className={m === info.best ? "text-emerald-300" : ""}>
                  <td>{m}</td><td>{r.mae}</td><td>{r.rmse}</td>
                  <td>{r.skill_vs_persistence == null ? "–" : `${(r.skill_vs_persistence * 100).toFixed(0)}%`}</td><td>{r.n}</td>
                </tr>))}</tbody>
            </table>
          </div>
        )) : <p className="text-sm text-slate-500">{btMsg || "Loading…"}</p>}
        <p className="mt-2 text-xs text-slate-500">Lower MAE is better. Skill above 0% means the model beats simply repeating the last value.</p>
      </section>

      <div className="flex flex-wrap items-center gap-2 text-sm">
        <span className="text-slate-400">Station:</span>
        {stations.map((s) => <button key={s} onClick={() => setSid(s)} className={`rounded-md px-2 py-1 text-xs ${s === sid ? "bg-emerald-500 text-slate-950" : "bg-slate-800"}`}>{s}</button>)}
      </div>

      <section className="grid gap-4 md:grid-cols-2">
        <div className="glass p-4">
          <p className="mb-2 text-sm font-semibold">Why is the +24 h PM2.5 forecast what it is?</p>
          {ex ? (<><p className="text-sm">{ex.text}</p>
            <div className="mt-3 grid grid-cols-3 gap-2 text-center text-xs">
              {Object.entries(ex.components).map(([k, v]) => <div key={k} className="glass-sm p-2"><p className="text-slate-400">{k.replace("_", " ")}</p><p className="text-lg font-semibold">{v}</p></div>)}
            </div></>) : <p className="text-sm text-slate-500">{exMsg || "Loading…"}</p>}
        </div>
        <div className="glass p-4">
          <p className="mb-2 text-sm font-semibold">Anomalies, last 48 h (Isolation Forest)</p>
          {an === null ? <p className="text-sm text-slate-500">Loading…</p> : an.length === 0 ? <p className="text-sm text-emerald-300">No unusual hours detected.</p> : (
            <ul className="space-y-1 text-sm">{an.slice(0, 8).map((a) => (
              <li key={a.time} className="rounded bg-slate-900/60 px-2 py-1">{new Date(a.time).toLocaleString()} · <b>{a.top_feature}</b> {a.value} ({a.robust_z > 0 ? "+" : ""}{a.robust_z}σ)</li>))}</ul>)}
        </div>
      </section>
    </main>
  );
}
