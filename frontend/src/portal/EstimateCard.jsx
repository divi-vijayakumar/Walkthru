import { money, range } from "@/shared/format";

export const EstimateCard = ({ quote, contractor }) => (
  <div data-testid="live-estimate-card" className="rounded-2xl bg-white p-5 text-wt-ink">
    <div className="flex items-center justify-between">
      <div className="flex items-center gap-2">
        <span className="text-[15px] font-bold">Your estimate</span>
        {quote && (
          <span data-testid="estimate-version" className="rounded-md bg-wt-soft px-1.5 py-0.5 text-xs font-bold text-wt-accentDark">
            v{quote.version}
          </span>
        )}
      </div>
      <span className="text-[13px] text-wt-muted">Estimate, not final</span>
    </div>
    {!quote && <p className="mt-3 text-[15px] text-wt-muted">Your estimate appears here as we talk.</p>}
    {quote && (
      <>
        <p data-testid="estimate-range" className="mt-1 font-display text-[28px] font-bold leading-tight tabular">{range(quote)}</p>
        <ul className="mt-3 border-t border-wt-line">
          {quote.line_items.map((i) => (
            <li key={i.key} data-testid={`estimate-line-${i.key}`}
              className={`flex items-center justify-between gap-3 border-b border-wt-line px-2 py-2.5 text-[15px] last:border-0 ${i.is_new ? "-mx-0 rounded-lg bg-wt-soft/70" : ""}`}>
              <span className="flex items-center gap-2">
                {i.label}
                {i.is_new && <span className="rounded bg-wt-soft px-1.5 text-[11px] font-bold text-wt-accentDark">NEW</span>}
              </span>
              <span className="font-bold tabular">{i.amount < 0 ? `-${money(-i.amount)}` : money(i.amount)}</span>
            </li>
          ))}
        </ul>
      </>
    )}
    <p className="mt-3 text-[13px] text-wt-muted">{contractor} confirms the final price after a quick site check.</p>
  </div>
);
