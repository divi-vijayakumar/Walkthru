import { clock, range } from "@/shared/format";

export const EqBars = ({ count = 7, className = "h-6", color = "bg-wt-accent" }) => (
  <div className={`flex items-end gap-[3px] ${className}`} aria-hidden="true">
    {Array.from({ length: count }).map((_, i) => (
      <span key={i} className={`eq-bar w-[4px] rounded-sm ${color}`}
        style={{ height: "100%", animationDelay: `${(i * 137) % 700}ms` }} />
    ))}
  </div>
);

export const OnCallCard = ({ lead, now }) => {
  const live = lead.live;
  const secs = live ? (now - new Date(live.started_at).getTime()) / 1000 : 0;
  return (
    <div data-testid="on-call-card" className="mt-4 rounded-2xl bg-wt-ink p-4 text-white">
      <div className="flex items-center justify-between">
        <p className="flex items-center gap-2 text-sm font-bold">
          <span className="h-2.5 w-2.5 animate-pulse rounded-full bg-[#F97316]" /> On call now
        </p>
        <span data-testid="on-call-timer" className="text-sm font-semibold tabular">{clock(secs)}</span>
      </div>
      <EqBars className="mt-3 h-6" color="bg-[#F97316]" />
      <p data-testid="on-call-caption" className="mt-3 min-h-[40px] text-[14px] leading-relaxed text-white/90">
        {live?.live_caption ? `"${live.live_caption}"` : "Waiting for the homeowner to speak..."}
      </p>
      <div className="mt-3 flex items-center justify-between gap-3 border-t border-white/15 pt-3">
        <span className="text-[13px] text-white/70">
          {lead.quote ? `Live estimate, v${lead.quote.version}` : "Live estimate"}
        </span>
        <span data-testid="on-call-estimate" className="whitespace-nowrap text-[17px] font-bold tabular">
          {lead.quote ? range(lead.quote) : "Building..."}
        </span>
      </div>
    </div>
  );
};
