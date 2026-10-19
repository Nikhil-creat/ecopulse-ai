"use client";
import { useEffect, useRef, useState } from "react";
import { MessageCircle, Send, X } from "lucide-react";
import { getJSON } from "@/lib/api";
import { ChatMeta, streamChat } from "@/lib/sse";

type Msg = { role: "user" | "assistant"; text: string; sources?: ChatMeta["sources"] };
type Quick = { label: string; prompt: string };

export default function ChatDrawer({ city }: { city: string | null }) {
  const [open, setOpen] = useState(false);
  const [msgs, setMsgs] = useState<Msg[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [quick, setQuick] = useState<Quick[]>([]);
  const sid = useRef<string | undefined>(undefined);
  const end = useRef<HTMLDivElement>(null);

  useEffect(() => {
    getJSON<Quick[]>("/chat/quick-actions").then(setQuick).catch(() => setQuick([]));
  }, []);
  useEffect(() => end.current?.scrollIntoView({ behavior: "smooth" }), [msgs]);

  const send = async (text: string) => {
    if (!text.trim() || busy) return;
    setInput("");
    setBusy(true);
    setMsgs((m) => [...m, { role: "user", text }, { role: "assistant", text: "" }]);
    const patch = (fn: (m: Msg) => Msg) =>
      setMsgs((all) => all.map((m, i) => (i === all.length - 1 ? fn(m) : m)));
    try {
      await streamChat(
        { message: text, city: city ?? undefined, session_id: sid.current },
        {
          onMeta: (meta) => { sid.current = meta.session_id; patch((m) => ({ ...m, sources: meta.sources })); },
          onToken: (t) => patch((m) => ({ ...m, text: m.text + t })),
          onError: (e) => patch((m) => ({ ...m, text: m.text || `⚠ ${e}` })),
        },
      );
    } catch {
      patch((m) => ({ ...m, text: m.text || "⚠ Connection error" }));
    } finally {
      setBusy(false);
    }
  };

  return (
    <>
      <button onClick={() => setOpen(true)} aria-label="Open assistant"
        className="fixed bottom-5 right-5 z-30 flex h-14 w-14 items-center justify-center rounded-full bg-emerald-500 text-slate-950 shadow-lg hover:bg-emerald-400">
        <MessageCircle />
      </button>
      {open && (
        <aside className="fixed bottom-0 right-0 z-40 flex h-[85vh] w-full flex-col rounded-t-2xl border border-slate-700 bg-slate-950 shadow-2xl sm:bottom-5 sm:right-5 sm:h-[600px] sm:w-[400px] sm:rounded-2xl">
          <header className="flex items-center justify-between border-b border-slate-800 px-4 py-3">
            <div>
              <p className="font-semibold">EcoPulse Assistant</p>
              <p className="text-xs text-slate-500">{city ? `Context: ${city}` : "No city selected"} · general guidance, not medical advice</p>
            </div>
            <button onClick={() => setOpen(false)} aria-label="Close"><X size={18} /></button>
          </header>
          <div className="flex-1 space-y-3 overflow-y-auto px-4 py-3 text-sm">
            {msgs.length === 0 && (
              <div className="space-y-2">
                <p className="text-slate-400">Ask about air quality, health precautions or policy measures.</p>
                {quick.map((q) => (
                  <button key={q.label} onClick={() => send(q.prompt)}
                    className="block w-full rounded-lg border border-slate-800 px-3 py-2 text-left hover:bg-slate-900">
                    {q.label}
                  </button>
                ))}
              </div>
            )}
            {msgs.map((m, i) => (
              <div key={i} className={m.role === "user" ? "text-right" : ""}>
                <div className={`inline-block max-w-[90%] whitespace-pre-wrap rounded-2xl px-3 py-2 text-left ${m.role === "user" ? "bg-emerald-600 text-white" : "bg-slate-800"}`}>
                  {m.text || (busy && i === msgs.length - 1 ? "…" : "")}
                </div>
                {m.sources && m.sources.length > 0 && m.text && (
                  <p className="mt-1 text-[11px] text-slate-500">
                    {m.sources.map((s) => `[${s.ref}] ${s.source}`).join(" · ")}
                  </p>
                )}
              </div>
            ))}
            <div ref={end} />
          </div>
          <form className="flex gap-2 border-t border-slate-800 p-3" onSubmit={(e) => { e.preventDefault(); void send(input); }}>
            <input value={input} onChange={(e) => setInput(e.target.value)} placeholder="Ask a question…" maxLength={2000}
              className="flex-1 rounded-lg bg-slate-900 px-3 py-2 text-sm outline-none ring-1 ring-slate-800 focus:ring-emerald-500" />
            <button disabled={busy} className="rounded-lg bg-emerald-500 px-3 text-slate-950 disabled:opacity-50" aria-label="Send">
              <Send size={16} />
            </button>
          </form>
        </aside>
      )}
    </>
  );
}
