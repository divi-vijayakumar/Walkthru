import { FLOW, STATUS } from "@/shared/status";
import { duration } from "@/shared/format";

const CountCard = ({ status, count, className = "" }) => (
  <div data-testid={`funnel-${status}`} className={`rounded-xl border border-wt-line bg-white px-4 py-3.5 ${className}`}>
    <p className="text-[13px] font-medium text-wt-ink/80">{STATUS[status].label}</p>
    <p className="mt-1 font-display text-2xl font-bold text-wt-ink tabular">{count}</p>
  </div>
);

export const FunnelStrip = ({ counts, median }) => (
  <div className="mt-6 grid grid-cols-2 gap-3 sm:grid-cols-3 xl:grid-cols-6">
    {FLOW.slice(0, 6).map((s) => <CountCard key={s} status={s} count={counts[s] || 0} />)}
    <CountCard status="pending_deposit" count={counts.pending_deposit || 0} className="xl:col-span-2" />
    <CountCard status="deposit_received" count={counts.deposit_received || 0} className="xl:col-span-2" />
    <div data-testid="funnel-median" className="col-span-2 rounded-xl border border-[#F5C7A6] bg-wt-soft px-4 py-3.5 sm:col-span-1 xl:col-span-2">
      <p className="text-[13px] font-semibold text-[#8A2F0B]">Median time to quote</p>
      <p className="mt-1 font-display text-2xl font-bold text-wt-accentDark tabular">{duration(median)}</p>
    </div>
  </div>
);
