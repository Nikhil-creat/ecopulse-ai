"use client";
import { useEffect, useState } from "react";
import { getJSON } from "@/lib/api";

type Ready = { status: string; checks: Record<string, string> };
type Drift = { status: string; retrain_recommended: boolean };

export default function SystemStatus() {
  const [ready, setReady] = useState<Ready | null>(null);
  const [drift, setDrift] = useState<Drift | null>(null);

  useEffect(() => {
    const load = () => {
      getJSON<Ready>("/health/ready").then(setReady).catch(() => setReady(null));
      getJSON<Drift>("/mlops/drift").then(setDrift).catch(() => setDrift(null));
    };
    load();
    const id = setInterval(load, 30000);
    return () => clearInterval(id);
  }, []);

  const ok = (v?: string) => v === "ok";
  const chips: { label: string; good: boolean | null; detail: string }[] = [
    { label: "TimescaleDB", good: ready ? ok(ready.checks.postgres) : null, detail: ready?.checks.extensions ?? "" },
    { label: "Redis", good: ready ? ok(ready.checks.redis) : null, detail: "" },
    { label: "Model drift", good: drift ? drift.status !== "drift" : null, detail: drift ? drift.status.replace("_", " ") : "no report" },
  ];
  return (
    <div className="flex flex-wrap gap-2 text-xs" aria-label="System status">
      {chips.map((c) => (
        <span key={c.label} className="glass-sm flex items-center gap-2 px-3 py-1.5">
          <span className={`h-2 w-2 rounded-full ${c.good === null ? "bg-slate-500" : c.good ? "bg-emerald-400 shadow-[0_0_8px_#34d399]" : "bg-red-500"}`} />
          {c.label}
          {c.detail && <span className="text-slate-500">{c.detail}</span>}
        </span>
      ))}
    </div>
  );
}
