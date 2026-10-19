"use client";
import dynamic from "next/dynamic";
import { useCallback, useEffect, useState } from "react";
import { API, Reading, SatelliteAnalysis, getJSON } from "@/lib/api";
import type { MapKind } from "./SpatialMapInner";

const Inner = dynamic(() => import("./SpatialMapInner"), {
  ssr: false,
  loading: () => <div className="flex h-full items-center justify-center text-slate-500">Loading 3D map…</div>,
});

export default function SpatialMap({ city, readings, onSelect }: { city: string; readings: Reading[]; onSelect: (id: string) => void }) {
  const [analysis, setAnalysis] = useState<SatelliteAnalysis | null>(null);
  const [kind, setKind] = useState<MapKind>("smog");
  const [msg, setMsg] = useState("");

  const load = useCallback(() => {
    getJSON<SatelliteAnalysis[]>(`/satellite/latest?region=${encodeURIComponent(city)}&limit=1`)
      .then((d) => setAnalysis(d[0] ?? null))
      .catch(() => setAnalysis(null));
  }, [city]);
  useEffect(load, [load]);

  const upload = async (file: File) => {
    setMsg("Uploading…");
    const fd = new FormData();
    fd.append("file", file);
    fd.append("region", city);
    fd.append("image_type", "satellite");
    const res = await fetch(`${API}/satellite/analyze`, { method: "POST", body: fd });
    if (!res.ok) return setMsg(`Upload failed (${res.status})`);
    setMsg("Analysing with CNN…");
    setTimeout(() => { load(); setMsg(""); }, 8000);
  };

  return (
    <div className="rounded-2xl border border-slate-800 bg-slate-900/60 p-4">
      <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
        <p className="text-sm font-semibold">3D spatial view</p>
        <div className="flex items-center gap-2 text-xs">
          {(["smog", "canopy"] as const).map((k) => (
            <button key={k} onClick={() => setKind(k)}
              className={`rounded-md px-2 py-1 ${k === kind ? "bg-emerald-500 text-slate-950" : "bg-slate-800 text-slate-300"}`}>
              {k === "smog" ? "Smog" : "Green canopy"}
            </button>
          ))}
          <label className="cursor-pointer rounded-md bg-slate-800 px-2 py-1 text-slate-300 hover:bg-slate-700">
            Upload image
            <input type="file" accept=".jpg,.jpeg,.png,.tif,.tiff" className="hidden"
              onChange={(e) => e.target.files?.[0] && upload(e.target.files[0])} />
          </label>
        </div>
      </div>
      <div className="h-[420px] overflow-hidden rounded-xl">
        <Inner readings={readings} heatmap={analysis?.heatmap ?? null} kind={kind} onSelect={onSelect} />
      </div>
      <p className="mt-1 text-xs text-slate-500">
        {msg ||
          (analysis
            ? `CNN analysis ${new Date(analysis.captured_at).toLocaleString()} · smog index ${analysis.smog_severity_index.toFixed(0)} · canopy ${(analysis.green_canopy_density * 100).toFixed(0)}% · ${analysis.model_version}. Grid is centred on the stations (no georeference).`
            : "No satellite analysis yet. Upload an image to render the CNN heatmap. Columns = station AQI.")}
      </p>
    </div>
  );
}
