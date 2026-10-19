"use client";
import { useCallback, useEffect, useState } from "react";
import { BellRing, Trash2 } from "lucide-react";
import { API } from "@/lib/api";

type Alert = { id: string; city: string; pollutant: string; threshold: number; severity: string; status: string; message: string | null };
const POLLUTANTS = ["aqi", "pm25", "pm10", "no2"] as const;

export default function AlertsPanel({ city }: { city: string }) {
  const [alerts, setAlerts] = useState<Alert[] | null>(null);
  const [authed, setAuthed] = useState(true);
  const [pollutant, setPollutant] = useState<string>("aqi");
  const [threshold, setThreshold] = useState("200");

  const load = useCallback(async () => {
    const r = await fetch(`${API}/alerts`);
    if (r.status === 401) { setAuthed(false); return setAlerts(null); }
    setAuthed(true);
    setAlerts(r.ok ? ((await r.json()) as Alert[]) : []);
  }, []);
  useEffect(() => {
    void load();
    const id = setInterval(() => void load(), 30000);
    window.addEventListener("ecopulse-auth", load);
    return () => { clearInterval(id); window.removeEventListener("ecopulse-auth", load); };
  }, [load]);

  const add = async (e: React.FormEvent) => {
    e.preventDefault();
    await fetch(`${API}/alerts`, { method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ city, pollutant, threshold: Number(threshold), severity: "warning" }) });
    await load();
  };
  const act = async (id: string, m: "POST" | "DELETE") => {
    await fetch(`${API}/alerts/${id}${m === "POST" ? "/rearm" : ""}`, { method: m });
    await load();
  };

  return (
    <section className="glass p-4">
      <p className="mb-2 flex items-center gap-2 text-sm font-semibold"><BellRing size={16} /> My alerts</p>
      {!authed && <p className="text-sm text-slate-400">Sign in to create threshold alerts for {city}.</p>}
      {authed && (
        <>
          <form onSubmit={add} className="mb-3 flex flex-wrap items-center gap-2 text-sm">
            <span className="text-slate-400">Notify me when {city}</span>
            <select value={pollutant} onChange={(e) => setPollutant(e.target.value)} className="rounded bg-slate-950/70 px-2 py-1 ring-1 ring-slate-700">
              {POLLUTANTS.map((p) => <option key={p}>{p}</option>)}
            </select>
            <span className="text-slate-400">reaches</span>
            <input type="number" min={1} value={threshold} onChange={(e) => setThreshold(e.target.value)} className="w-20 rounded bg-slate-950/70 px-2 py-1 ring-1 ring-slate-700" />
            <button className="rounded bg-emerald-500 px-3 py-1 font-medium text-slate-950">Add</button>
          </form>
          <ul className="space-y-2 text-sm">
            {alerts?.length === 0 && <li className="text-slate-500">No alerts yet.</li>}
            {alerts?.map((a) => (
              <li key={a.id} className={`flex items-center justify-between rounded-lg px-3 py-2 ${a.status === "triggered" ? "bg-red-950/60 ring-1 ring-red-500/50" : "bg-slate-900/60"}`}>
                <span>{a.status === "triggered" ? `🔔 ${a.message}` : `${a.city}: ${a.pollutant.toUpperCase()} ≥ ${a.threshold}`}</span>
                <span className="flex gap-3">
                  {a.status === "triggered" && <button onClick={() => act(a.id, "POST")} className="text-xs text-cyan-300">Re-arm</button>}
                  <button onClick={() => act(a.id, "DELETE")} aria-label="Delete alert"><Trash2 size={14} /></button>
                </span>
              </li>
            ))}
          </ul>
        </>
      )}
    </section>
  );
}
