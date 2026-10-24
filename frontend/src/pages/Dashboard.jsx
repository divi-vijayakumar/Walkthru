import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { LeadsTable } from "@/components/LeadsTable";
import { Skeleton } from "@/components/ui/skeleton";
import { DASHBOARD } from "@/constants/testIds";

const Stat = ({ label, value, accent, id }) => (
  <div data-testid={DASHBOARD.stat(id)} className="rounded-xl border border-zinc-800 bg-[#18181b] px-5 py-4">
    <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-zinc-500">{label}</p>
    <p className={`mt-2 font-display text-3xl font-bold ${accent ? "text-orange-500" : "text-zinc-50"}`}>{value}</p>
  </div>
);

export default function Dashboard() {
  const [leads, setLeads] = useState(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    document.title = "Leads · Walkthru";
    api.get("/leads").then((r) => setLeads(r.data)).catch(() => setError(true));
  }, []);

  const count = (s) => (leads || []).filter((l) => l.status === s).length;

  return (
    <div data-testid={DASHBOARD.page} className="mx-auto max-w-6xl px-5 py-10 sm:px-8 lg:px-12 lg:py-14">
      <p className="font-mono text-xs uppercase tracking-[0.2em] text-orange-500">Inbox</p>
      <h1 data-testid={DASHBOARD.title} className="mt-2 text-4xl font-extrabold tracking-tight text-zinc-50 sm:text-5xl">
        Leads
      </h1>
      <p className="mt-3 max-w-xl text-sm text-zinc-400 md:text-base">
        Customer video walkthroughs waiting for scope and a quote.
      </p>

      <div className="mt-10 grid grid-cols-3 gap-3 sm:gap-4">
        <Stat id="total" label="Total leads" value={leads ? leads.length : "–"} />
        <Stat id="new" label="New" value={leads ? count("new") : "–"} accent />
        <Stat id="quoted" label="Quoted" value={leads ? count("quoted") : "–"} />
      </div>

      <div className="mt-8">
        {error && (
          <p data-testid={DASHBOARD.error} className="rounded-lg border border-red-500/30 bg-red-500/10 p-4 text-sm text-red-300">
            Couldn't load leads. Please refresh.
          </p>
        )}
        {!leads && !error && (
          <div data-testid={DASHBOARD.loading} className="space-y-2">
            {[0, 1, 2].map((i) => <Skeleton key={i} className="h-16 w-full bg-zinc-800/60" />)}
          </div>
        )}
        {leads && <LeadsTable leads={leads} />}
      </div>
    </div>
  );
}
