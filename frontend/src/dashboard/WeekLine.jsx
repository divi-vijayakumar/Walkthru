import { useState } from "react";
import { toast } from "sonner";
import { api, errorText } from "@/shared/api";
import { when } from "@/dashboard/CallDetail";

const WEEK = [["invited", "invited"], ["completed", "completed"], ["quotes", "quotes given"], ["contracts", "contracts executed"], ["new", "new leads"]];

export const WeekLine = ({ week, active, onPick }) => (
  <p data-testid="week-line" className="mt-5 flex flex-wrap items-center gap-x-2 gap-y-1 rounded-xl border border-wt-line bg-white px-4 py-3 text-[15px] text-wt-ink">
    <span className="font-bold">Walkthru's last 7 days:</span>
    {WEEK.map(([k, label], i) => (
      <span key={k} className="flex items-center gap-2">
        {i > 0 && <span className="text-wt-muted">·</span>}
        <button data-testid={`week-${k}`} onClick={() => onPick(active === k ? null : k)}
          className={`rounded-md px-1.5 py-0.5 transition-colors ${active === k ? "bg-wt-accent text-white" : "hover:bg-wt-soft"}`}>
          <b className="tabular">{week?.[k]?.length ?? 0}</b> {label}
        </button>
      </span>
    ))}
  </p>
);

const VisitRow = ({ v, onDone }) => {
  const [time, setTime] = useState("");
  const save = async () => {
    if (!time) return toast.error("Pick a date and time first");
    const label = new Date(time).toLocaleString("en-US", { weekday: "long", month: "short", day: "numeric", hour: "numeric", minute: "2-digit" });
    try {
      await api.post(`/leads/${v.id}/visit`, { when: label });
      toast.success(`Visit set for ${label}`, { description: `${v.name} got a WhatsApp confirmation` });
      onDone();
    } catch (e) { toast.error(errorText(e)); }
  };
  return (
    <div data-testid={`visit-row-${v.id}`} className="flex flex-wrap items-center gap-3 border-t border-wt-line py-3 text-[14px]">
      <span className="min-w-[140px] font-bold text-wt-ink">{v.name}</span>
      <span className="text-wt-muted">{v.phone}</span>
      <span className="flex-1">{v.visit_times || "No times given"} · asked {when(v.visit_requested_at)}</span>
      {v.visit_scheduled_for ? <span data-testid={`visit-scheduled-${v.id}`} className="rounded-md bg-[#CCFBF1] px-2 py-1 text-xs font-bold text-wt-teal">Visit scheduled: {v.visit_scheduled_for}</span> : (
        <>
          <input data-testid={`visit-time-${v.id}`} type="datetime-local" value={time} onChange={(e) => setTime(e.target.value)} className="rounded-lg border border-wt-line px-2 py-1.5" />
          <button data-testid={`visit-schedule-${v.id}`} onClick={save} className="rounded-lg bg-wt-accent px-3 py-2 font-bold text-white hover:bg-wt-accentDark">Mark scheduled</button>
        </>
      )}
      <a data-testid={`visit-call-${v.id}`} href={`tel:${v.phone}`} className="rounded-lg border border-wt-line px-3 py-2 font-bold text-wt-ink">Call</a>
    </div>
  );
};

export const VisitSection = ({ visits, onDone }) => (visits?.length ? (
  <section data-testid="visit-section" className="mt-5 rounded-2xl border border-wt-line bg-white px-4 py-3">
    <h2 className="text-base font-bold text-wt-ink md:text-lg">In-person visit requested</h2>
    {visits.map((v) => <VisitRow key={v.id} v={v} onDone={onDone} />)}
  </section>
) : null);
