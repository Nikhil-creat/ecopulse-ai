"use client";
import { AQI_BANDS, aqiBand } from "@/lib/api";

const CX = 120, CY = 120, R = 95;
const pt = (v: number, r = R): [number, number] => {
  const a = Math.PI * (1 - Math.min(Math.max(v, 0), 500) / 500);
  return [CX + r * Math.cos(a), CY - r * Math.sin(a)];
};
const arc = (from: number, to: number) => {
  const [x1, y1] = pt(from);
  const [x2, y2] = pt(to);
  return `M ${x1} ${y1} A ${R} ${R} 0 0 1 ${x2} ${y2}`;
};

export default function AqiGauge({ aqi, label }: { aqi: number | null; label?: string }) {
  const band = aqiBand(aqi);
  const [nx, ny] = pt(aqi ?? 0, R - 18);
  return (
    <div className="rounded-2xl border border-slate-800 bg-slate-900/60 p-4">
      <p className="text-xs uppercase tracking-wider text-slate-400">{label ?? "Air Quality Index"}</p>
      <svg viewBox="0 0 240 140" className="mx-auto w-full max-w-xs">
        {AQI_BANDS.map((b, i) => (
          <path key={b.label} d={arc(i === 0 ? 0 : AQI_BANDS[i - 1].max, b.max)} stroke={b.color} strokeWidth="14" fill="none" />
        ))}
        {aqi != null && (
          <>
            <line x1={CX} y1={CY} x2={nx} y2={ny} stroke="#e2e8f0" strokeWidth="3" strokeLinecap="round" />
            <circle cx={CX} cy={CY} r="6" fill="#e2e8f0" />
          </>
        )}
        <text x={CX} y={CY - 28} textAnchor="middle" className="fill-slate-100" fontSize="30" fontWeight="700">
          {aqi != null ? Math.round(aqi) : "--"}
        </text>
      </svg>
      <p className="-mt-2 text-center text-lg font-semibold" style={{ color: band.color }}>{band.label}</p>
    </div>
  );
}
