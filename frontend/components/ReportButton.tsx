"use client";
import { useState } from "react";
import { Download, Loader2 } from "lucide-react";
import { API } from "@/lib/api";

export default function ReportButton({ city }: { city: string }) {
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  const download = async () => {
    setBusy(true);
    setErr("");
    try {
      const res = await fetch(`${API}/reports/executive?city=${encodeURIComponent(city)}`);
      if (!res.ok) throw new Error(String(res.status));
      const url = URL.createObjectURL(await res.blob());
      const a = document.createElement("a");
      a.href = url;
      a.download = `ecopulse-report-${city.toLowerCase().replace(/\s+/g, "-")}.pdf`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (e) {
      setErr(`Report failed (${(e as Error).message})`);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="flex items-center gap-2">
      <button onClick={download} disabled={busy}
        className="flex items-center gap-2 rounded-lg bg-emerald-500 px-3 py-2 text-sm font-medium text-slate-950 hover:bg-emerald-400 disabled:opacity-60">
        {busy ? <Loader2 size={16} className="animate-spin" /> : <Download size={16} />}
        Executive Health &amp; Policy Report
      </button>
      {err && <span className="text-xs text-red-400">{err}</span>}
    </div>
  );
}
