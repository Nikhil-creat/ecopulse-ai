"use client";
import { useMemo } from "react";
import DeckGL from "@deck.gl/react";
import { ColumnLayer, GridCellLayer } from "@deck.gl/layers";
import { HeatmapData, Reading, aqiBand, hexToRgb } from "@/lib/api";

export type MapKind = "smog" | "canopy";
type Cell = { position: [number, number]; value: number };
const EXTENT = 0.06; // degrees (~6.5 km) used when the analysis has no bbox

function ramp(v: number, kind: MapKind): [number, number, number, number] {
  const c = Math.min(Math.max(v, 0), 1);
  return kind === "smog"
    ? [Math.round(40 + 215 * c), Math.round(200 - 150 * c), 60, 210]
    : [30, Math.round(60 + 180 * c), 70, 210];
}

export default function SpatialMapInner(props: {
  readings: Reading[];
  heatmap: HeatmapData | null;
  kind: MapKind;
  onSelect: (stationId: string) => void;
}) {
  const { readings, heatmap, kind, onSelect } = props;
  const located = readings.filter((r) => r.latitude != null && r.longitude != null);

  const center = useMemo<[number, number]>(() => {
    if (!located.length) return [79.59, 17.97];
    return [
      located.reduce((s, r) => s + (r.longitude as number), 0) / located.length,
      located.reduce((s, r) => s + (r.latitude as number), 0) / located.length,
    ];
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [located.map((r) => r.station_id).join(",")]);

  const cells = useMemo<Cell[]>(() => {
    if (!heatmap) return [];
    const g = heatmap.grid;
    const grid = heatmap[kind];
    const out: Cell[] = [];
    for (let i = 0; i < g; i++)
      for (let j = 0; j < g; j++)
        out.push({
          position: [center[0] - EXTENT + ((j + 0.5) * 2 * EXTENT) / g, center[1] + EXTENT - ((i + 0.5) * 2 * EXTENT) / g],
          value: grid[i][j],
        });
    return out;
  }, [heatmap, kind, center]);

  const cellMeters = (2 * EXTENT * 111_320) / (heatmap?.grid ?? 16);

  const layers = [
    new GridCellLayer<Cell>({
      id: "cnn-grid",
      data: cells,
      getPosition: (d) => d.position,
      getFillColor: (d) => ramp(d.value, kind),
      getElevation: (d) => d.value * (kind === "smog" ? 1800 : 900),
      cellSize: cellMeters,
      extruded: true,
      pickable: true,
    }),
    new ColumnLayer<Reading>({
      id: "stations",
      data: located,
      getPosition: (d) => [d.longitude as number, d.latitude as number],
      getFillColor: (d) => [...hexToRgb(aqiBand(d.aqi).color), 240] as [number, number, number, number],
      getElevation: (d) => (d.aqi ?? 0) * 12,
      radius: 350,
      diskResolution: 24,
      extruded: true,
      pickable: true,
      onClick: (info) => info.object && onSelect((info.object as Reading).station_id),
    }),
  ];

  return (
    <DeckGL
      key={center.join(",")}
      initialViewState={{ longitude: center[0], latitude: center[1], zoom: 10.3, pitch: 55, bearing: -15 }}
      controller
      layers={layers}
      style={{ position: "relative", width: "100%", height: "100%", background: "#0b1220" }}
      getTooltip={({ object }) => {
        if (!object) return null;
        if ("station_id" in (object as object)) {
          const r = object as Reading;
          return `${r.station_id}\nAQI ${r.aqi ?? "--"} (${aqiBand(r.aqi).label})`;
        }
        return `${kind} ${(object as Cell).value.toFixed(2)}`;
      }}
    />
  );
}
