"use client";
import { useEffect, useRef, useState } from "react";
import type { Reading } from "./api";

export type LiveStatus = "connecting" | "live" | "offline";

export function useLiveMetrics(city: string | null) {
  const [readings, setReadings] = useState<Record<string, Reading>>({});
  const [status, setStatus] = useState<LiveStatus>("connecting");
  const retry = useRef(0);

  useEffect(() => {
    if (!city) return;
    let ws: WebSocket | null = null;
    let timer: ReturnType<typeof setTimeout> | undefined;
    let closed = false;
    setReadings({});

    const connect = () => {
      setStatus("connecting");
      const url = new URL(process.env.NEXT_PUBLIC_WS_URL ?? "/ws/live-metrics", window.location.href);
      url.protocol = url.protocol.replace("http", "ws");
      url.searchParams.set("city", city);
      ws = new WebSocket(url.toString());
      ws.onopen = () => {
        retry.current = 0;
        setStatus("live");
      };
      ws.onmessage = (ev: MessageEvent<string>) => {
        const msg = JSON.parse(ev.data) as { type: string; data?: Reading[] };
        if (msg.type === "snapshot" && msg.data) {
          setReadings(Object.fromEntries(msg.data.map((r) => [r.station_id, r])));
        } else if (msg.type === "readings" && msg.data) {
          const batch = msg.data;
          setReadings((prev) => ({ ...prev, ...Object.fromEntries(batch.map((r) => [r.station_id, r])) }));
        }
      };
      ws.onclose = () => {
        if (closed) return;
        setStatus("offline");
        retry.current += 1;
        timer = setTimeout(connect, Math.min(30000, 1000 * 2 ** retry.current));
      };
      ws.onerror = () => ws?.close();
    };
    connect();
    return () => {
      closed = true;
      if (timer) clearTimeout(timer);
      ws?.close();
    };
  }, [city]);

  return { readings, status };
}
