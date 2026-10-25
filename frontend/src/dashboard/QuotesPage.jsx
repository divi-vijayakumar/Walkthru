import { useEffect, useMemo, useState } from "react";
import { api } from "@/shared/api";
import { money, range } from "@/shared/format";
import { when } from "@/dashboard/CallDetail";
import { Chips, PageShell, SampleTag, Stat } from "@/dashboard/PageShell";
import { QuoteDetail, QuoteStatus } from "@/dashboard/QuoteDetail";

const FILTERS = [["all", "All"], ["live", "In call"], ["sent", "Sent"], ["accepted", "Accepted"], ["recalled", "Recalled"]];

const QuoteRow = ({ q, active, onOpen }) => (
  <tr data-testid={`quote-row-${q.id}`} onClick={() => onOpen(q.id)}
    className={`cursor-pointer border-t border-wt-line transition-colors hover:bg-wt-soft ${active ? "bg-wt-soft" : ""}`}>
    <td className="px-4 py-3"><p className="font-bold text-wt-ink">{q.lead_name}<SampleTag show={q.sample} /></p><p className="text-[13px] text-wt-muted">{q.ask}</p></td>
    <td className="px-4 py-3 tabular">v{q.version}</td>
    <td className="px-4 py-3"><QuoteStatus status={q.status} /></td>
    <td className="px-4 py-3 font-bold tabular">{money(q.total)}</td>
    <td className="px-4 py-3 text-wt-muted tabular">{range(q)}</td>
    <td className="px-4 py-3">{when(q.created_at)}</td>
  </tr>
);

export default function QuotesPage() {
  const [data, setData] = useState(null);
  const [filter, setFilter] = useState("all");
  const [latestOnly, setLatestOnly] = useState(true);
  const [open, setOpen] = useState(null);
  useEffect(() => {
    document.title = "Quotes · Walkthru";
    api.get("/quotes").then((r) => setData(r.data)).catch(() => setData({ quotes: [], totals: {} }));
  }, []);
  const rows = useMemo(() => (data?.quotes || []).filter((q) => (!latestOnly || q.latest) && (filter === "all" || q.status === filter)), [data, filter, latestOnly]);
  const t = data?.totals || {};
  return (
    <PageShell testId="quotes-page" title="Quotes" subtitle="Every quote Alex has given, with each version. Download any quote as a PDF.">
      <div className="mt-6 grid gap-3 sm:grid-cols-3">
        <Stat testId="quotes-stat-open" label="Open quotes" value={money(t.open || 0)} note="Sent or in a call, latest versions" />
        <Stat testId="quotes-stat-accepted" label="Accepted" value={money(t.accepted || 0)} note="Signed contracts" />
        <Stat testId="quotes-stat-count" label="Active quotes" value={t.count ?? 0} note="One per lead, recalled left out" />
      </div>
      <div className="mt-5 flex flex-wrap items-center justify-between gap-3">
        <Chips prefix="quotes-filter" options={FILTERS} value={filter} onChange={setFilter} />
        <label className="flex min-h-[44px] items-center gap-2 text-[14px] font-semibold text-wt-ink">
          <input data-testid="quotes-latest-only" type="checkbox" checked={latestOnly} onChange={(e) => setLatestOnly(e.target.checked)} className="h-4 w-4 accent-[#C2410C]" />
          Latest version only
        </label>
      </div>
      <div className="mt-4 grid gap-4 xl:grid-cols-[1fr_420px]">
        <div className="overflow-x-auto rounded-2xl border border-wt-line bg-white">
          <table className="w-full min-w-[640px] text-left text-[14px]">
            <thead className="text-[13px] text-wt-muted"><tr>{["Lead", "Version", "Status", "Total", "Range", "Date"].map((h) => <th key={h} className="px-4 py-3 font-semibold">{h}</th>)}</tr></thead>
            <tbody>
              {rows.map((q) => <QuoteRow key={q.id} q={q} active={open === q.id} onOpen={setOpen} />)}
              {data && rows.length === 0 && <tr><td colSpan={6} data-testid="quotes-empty" className="px-4 py-6 text-wt-muted">No quotes here yet.</td></tr>}
            </tbody>
          </table>
        </div>
        <aside className="rounded-2xl border border-wt-line bg-white p-4">
          {open ? <QuoteDetail key={open} quoteId={open} onPick={setOpen} /> : <p className="text-[14px] text-wt-muted">Pick a quote to see its lines and download the PDF.</p>}
        </aside>
      </div>
    </PageShell>
  );
}
