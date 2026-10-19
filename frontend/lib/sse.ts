import { API } from "./api";

export type ChatMeta = { session_id: string; city: string | null; live_data: boolean; sources: { ref: string; source: string; title: string }[] };

export async function streamChat(
  body: { message: string; city?: string; session_id?: string },
  handlers: { onMeta: (m: ChatMeta) => void; onToken: (t: string) => void; onError: (m: string) => void },
  signal?: AbortSignal,
): Promise<void> {
  const res = await fetch(`${API}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    signal,
  });
  if (!res.ok || !res.body) {
    handlers.onError(`Request failed (${res.status})`);
    return;
  }
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buf = "";
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buf += decoder.decode(value, { stream: true });
    let idx: number;
    while ((idx = buf.indexOf("\n\n")) !== -1) {
      const block = buf.slice(0, idx);
      buf = buf.slice(idx + 2);
      let event = "message";
      let data = "";
      for (const line of block.split("\n")) {
        if (line.startsWith("event:")) event = line.slice(6).trim();
        else if (line.startsWith("data:")) data += line.slice(5).trim();
      }
      if (!data) continue;
      const parsed: unknown = JSON.parse(data);
      if (event === "meta") handlers.onMeta(parsed as ChatMeta);
      else if (event === "token") handlers.onToken(parsed as string);
      else if (event === "error") handlers.onError((parsed as { message: string }).message);
    }
  }
}
