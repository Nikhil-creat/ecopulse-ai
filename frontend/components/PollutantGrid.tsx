"use client";
import { Reading, WHO_24H } from "@/lib/api";

const ITEMS: { key: keyof Reading; label: string; unit: string }[] = [
  { key: "pm25", label: "PM2.5", unit: "µg/m³" },
  { key: "pm10", label: "PM10", unit: "µg/m³" },
  { key: "no2", label: "NO₂", unit: "µg/m³" },
  { key: "co", label: "CO", unit: "µg/m³" },
  { key: "temperature", label: "Temperature", unit: "°C" },
  { key: "humidity", label: "Humidity", unit: "%" },
];

export default function PollutantGrid({ reading }: { reading: Reading | null }) {
  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
      {ITEMS.map(({ key, label, unit }) => {
        const v = reading ? (reading[key] as number | null) : null;
        const who = WHO_24H[key as string];
        const ratio = v != null && who ? v / who : null;
        return (
          <div key={key} className="rounded-xl border border-slate-800 bg-slate-900/60 p-3">
            <p className="text-xs text-slate-400">{label}</p>
            <p className="text-2xl font-semibold">
              {v != null ? v.toFixed(v >= 100 ? 0 : 1) : "--"}
              <span className="ml-1 text-xs font-normal text-slate-500">{unit}</span>
            </p>
            {ratio != null && (
              <p className={`text-xs ${ratio > 1 ? "text-amber-400" : "text-emerald-400"}`}>
                {ratio.toFixed(1)}× WHO 24h guideline
              </p>
            )}
          </div>
        );
      })}
    </div>
  );
}
