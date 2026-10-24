import { useMemo, useState } from "react";
import { ALL_FILTER, FilterSelect } from "@/dashboard/FilterSelect";
import { LeadRow } from "@/dashboard/LeadRow";
import { STATUS, SOURCES } from "@/shared/status";

const HEADERS = ["Lead", "Source", "Ask", "Status", "Quote", "Last activity", "Action"];

export const LeadTable = ({ leads, selectedId, flash, now, onSelect, onAction }) => {
  const [status, setStatus] = useState(ALL_FILTER);
  const [source, setSource] = useState(ALL_FILTER);
  const [ask, setAsk] = useState(ALL_FILTER);
  const asks = useMemo(() => [...new Set(leads.map((l) => l.ask))].sort(), [leads]);
  const rows = leads.filter(
    (l) => (status === ALL_FILTER || l.status === status) && (source === ALL_FILTER || l.source === source) && (ask === ALL_FILTER || l.ask === ask),
  );

  return (
    <section className="min-w-0 overflow-hidden rounded-2xl border border-wt-line bg-white">
      <div className="flex flex-wrap items-center gap-x-5 gap-y-3 px-5 py-4">
        <h2 className="mr-auto text-[17px] font-bold text-wt-ink">All leads</h2>
        <FilterSelect id="status" label="Status" value={status} onChange={setStatus}
          options={Object.entries(STATUS).map(([v, s]) => [v, s.label])} />
        <FilterSelect id="source" label="Source" value={source} onChange={setSource} options={Object.entries(SOURCES)} />
        <FilterSelect id="ask" label="Ask" value={ask} onChange={setAsk} options={asks.map((a) => [a, a])} />
      </div>
      <div className="overflow-x-auto">
        <table data-testid="leads-table" className="w-full min-w-[920px] text-left">
          <thead>
            <tr className="text-[13px] font-semibold text-wt-muted">
              {HEADERS.map((h) => <th key={h} className="px-4 py-3 font-semibold">{h}</th>)}
            </tr>
          </thead>
          <tbody>
            {rows.map((l) => (
              <LeadRow key={l.id} lead={l} selected={l.id === selectedId} flash={!!flash[l.id]} now={now}
                onSelect={onSelect} onAction={onAction} />
            ))}
          </tbody>
        </table>
        {rows.length === 0 && (
          <p data-testid="leads-empty" className="border-t border-wt-line px-5 py-10 text-center text-sm text-wt-muted">
            No leads match these filters.
          </p>
        )}
      </div>
    </section>
  );
};
