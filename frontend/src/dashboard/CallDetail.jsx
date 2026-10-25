import { useEffect, useState } from "react";
import { api } from "@/shared/api";
import { money } from "@/shared/format";

export const duration = (s) => {
  if (s == null) return "";
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  return `${h ? `${h}h ` : ""}${m}m ${String(s % 60).padStart(2, "0")}s`;
};
export const when = (iso) => (iso ? new Date(iso).toLocaleString("en-US", { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" }) : "");

const Transcript = ({ lines }) => (
  <div data-testid="call-transcript" className="mt-3 max-h-72 space-y-2 overflow-y-auto rounded-xl bg-wt-ground p-3">
    {lines.length === 0 && <p className="text-[13px] text-wt-muted">No transcript saved.</p>}
    {lines.map((l, i) => (
      <p key={i} className="text-[14px] leading-snug">
        <span className={`font-bold ${l.role === "user" ? "text-wt-accent" : "text-wt-teal"}`}>
          {l.role === "user" ? "Homeowner" : l.role === "system" ? "System" : "Alex"}:
        </span>{" "}{l.text}
      </p>
    ))}
  </div>
);

const Findings = ({ items }) => (items.length ? (
  <div data-testid="call-findings" className="mt-3 grid grid-cols-2 gap-2">
    {items.map((f, i) => (
      <a key={i} href={f.frame_url} target="_blank" rel="noreferrer" className="overflow-hidden rounded-lg border border-wt-line bg-white">
        {f.frame_url && <img src={f.frame_url} alt={f.label || f.fact_id} className="h-24 w-full object-cover" />}
        <p className="p-2 text-[12px] leading-snug text-wt-ink">{(f.label || "").split(":").pop().trim() || f.explanation}</p>
      </a>
    ))}
  </div>
) : <p className="mt-2 text-[13px] text-wt-muted">No camera findings.</p>);

export const CallDetail = ({ callId }) => {
  const [c, setC] = useState(null);
  useEffect(() => { api.get(`/calls/${callId}`).then((r) => setC(r.data)).catch(() => setC(false)); }, [callId]);
  if (c === null) return <div className="h-32 animate-pulse rounded-xl bg-wt-ground" />;
  if (!c) return <p className="text-[13px] text-wt-muted">Couldn't load this call.</p>;
  return (
    <div data-testid={`call-detail-${callId}`}>
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <p className="text-[15px] font-bold text-wt-ink">{when(c.started_at)} · {duration(c.duration_s)}</p>
        <span data-testid="call-outcome" className="rounded-md bg-[#E9ECF1] px-2 py-0.5 text-xs font-semibold text-wt-ink">{c.outcome}</span>
      </div>
      {c.recording ? <audio data-testid="call-recording" controls src={c.recording} className="mt-3 w-full" />
        : <p className="mt-2 text-[13px] text-wt-muted">No recording saved.</p>}
      {c.summary && <p className="mt-2 text-[14px] text-wt-muted">{c.summary}</p>}
      <Transcript lines={c.transcript} />
      <p className="mt-4 text-sm font-bold text-wt-ink">What the camera saw</p>
      <Findings items={c.findings} />
      {c.quotes.length > 0 && (
        <div className="mt-4">
          <p className="text-sm font-bold text-wt-ink">Quote versions in this call</p>
          {c.quotes.map((q) => <p key={q.version} className="text-[14px] tabular">v{q.version} · {money(q.total)} · {q.status}</p>)}
        </div>
      )}
    </div>
  );
};

export const CallCard = ({ callId }) => (
  <div data-testid="call-card" className="mt-4 rounded-xl border border-wt-line p-3.5">
    <p className="mb-2 text-sm font-bold text-wt-ink">Call</p>
    <CallDetail callId={callId} />
  </div>
);
