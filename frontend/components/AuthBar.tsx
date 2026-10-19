"use client";
import { useEffect, useState } from "react";
import { LogIn, LogOut } from "lucide-react";
import { API } from "@/lib/api";

type Me = { email: string; role: string };

export default function AuthBar() {
  const [me, setMe] = useState<Me | null>(null);
  const [open, setOpen] = useState(false);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [err, setErr] = useState("");

  const load = () =>
    fetch(`${API}/auth/me`).then((r) => (r.ok ? r.json() : null)).then(setMe).catch(() => setMe(null));
  useEffect(() => { void load(); }, []);

  const login = async (e: React.FormEvent) => {
    e.preventDefault();
    setErr("");
    const r = await fetch(`${API}/auth/login`, {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ email, password }),
    });
    if (!r.ok) return setErr(r.status === 429 ? "Too many attempts, wait a minute" : "Invalid email or password");
    setPassword(""); setOpen(false); await load(); window.dispatchEvent(new Event("ecopulse-auth"));
  };
  const logout = async () => { await fetch(`${API}/auth/logout`, { method: "POST" }); setMe(null); window.dispatchEvent(new Event("ecopulse-auth")); };

  if (me)
    return (
      <span className="glass-sm flex items-center gap-2 px-3 py-1.5 text-xs">
        {me.email} <span className="rounded bg-cyan-500/20 px-1.5 text-cyan-300">{me.role}</span>
        <button onClick={logout} aria-label="Log out"><LogOut size={14} /></button>
      </span>
    );
  return (
    <div className="relative">
      <button onClick={() => setOpen(!open)} className="glass-sm flex items-center gap-2 px-3 py-1.5 text-xs"><LogIn size={14} /> Sign in</button>
      {open && (
        <form onSubmit={login} className="glass absolute right-0 z-20 mt-2 w-64 space-y-2 p-3 text-sm">
          <input type="email" required value={email} onChange={(e) => setEmail(e.target.value)} placeholder="Email" autoComplete="username"
            className="w-full rounded bg-slate-950/70 px-2 py-1.5 ring-1 ring-slate-700" />
          <input type="password" required value={password} onChange={(e) => setPassword(e.target.value)} placeholder="Password" autoComplete="current-password"
            className="w-full rounded bg-slate-950/70 px-2 py-1.5 ring-1 ring-slate-700" />
          {err && <p className="text-xs text-red-400">{err}</p>}
          <button className="w-full rounded bg-emerald-500 py-1.5 font-medium text-slate-950">Sign in</button>
        </form>
      )}
    </div>
  );
}
