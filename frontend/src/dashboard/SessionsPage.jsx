import { useEffect, useState } from "react";
import { api } from "@/shared/api";
import { money } from "@/shared/format";
import { Sidebar } from "@/dashboard/Sidebar";
import { CallDetail, duration, when } from "@/dashboard/CallDetail";

export default function SessionsPage() {
  const [calls, setCalls] = useState(null);
  const [open, setOpen] = useState(null);
  useEffect(() => {
    document.title = "Sessions · Walkthru";
    api.get("/calls").then((r) => setCalls(r.data.calls)).catch(() => setCalls([]));
  }, []);
  return (
    <div className="min-h-screen bg-wt-ground lg:flex">
      <Sidebar />
      <main data-testid="sessions-page" className="min-w-0 flex-1 px-4 py-6 sm:px-6 lg:px-8 lg:py-8">
        <h1 className="font-display text-4xl font-bold tracking-tight text-wt-ink">Sessions</h1>
        <p className="mt-1.5 text-[15px] text-wt-muted">Every call Alex has had, with the recording, transcript and what the camera saw.</p>
        <div className="mt-6 grid gap-4 xl:grid-cols-[1fr_440px]">
          <div className="overflow-x-auto rounded-2xl border border-wt-line bg-white">
            <table className="w-full text-left text-[14px]">
              <thead className="text-[13px] text-wt-muted"><tr>{["Lead", "Date", "Duration", "Outcome", "Quote"].map((h) => <th key={h} className="px-4 py-3 font-semibold">{h}</th>)}</tr></thead>
              <tbody>
                {(calls || []).map((c) => (
                  <tr key={c.id} data-testid={`session-row-${c.id}`} onClick={() => setOpen(c.id)}
                    className={`cursor-pointer border-t border-wt-line transition-colors hover:bg-wt-soft ${open === c.id ? "bg-wt-soft" : ""}`}>
                    <td className="px-4 py-3 font-bold text-wt-ink">{c.lead_name}{c.sample && <span className="ml-2 text-xs font-semibold text-wt-muted">sample</span>}</td>
                    <td className="px-4 py-3">{when(c.started_at)}</td>
                    <td className="px-4 py-3 tabular">{c.ended_at ? duration(c.duration_s) : "Live"}</td>
                    <td className="px-4 py-3">{c.outcome}</td>
                    <td className="px-4 py-3 tabular">{money(c.quote_total)}</td>
                  </tr>
                ))}
                {calls && calls.length === 0 && <tr><td colSpan={5} className="px-4 py-6 text-wt-muted">No calls yet.</td></tr>}
              </tbody>
            </table>
          </div>
          <aside className="rounded-2xl border border-wt-line bg-white p-4">
            {open ? <CallDetail key={open} callId={open} /> : <p className="text-[14px] text-wt-muted">Pick a call to see the details.</p>}
          </aside>
        </div>
      </main>
    </div>
  );
}
