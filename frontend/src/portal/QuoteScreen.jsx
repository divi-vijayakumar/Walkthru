import { useState } from "react";
import { Mic } from "lucide-react";
import { money, range } from "@/shared/format";
import { SeenFrame } from "@/shared/SeenFrame";
import { QuotePdfLink } from "@/shared/QuotePdfLink";
import { PortalHeader, PortalShell, PrimaryButton, Row, Steps } from "@/portal/PortalShell";

export const LineItems = ({ quote }) => (
  <ul className="mt-3">
    {quote.line_items.map((i) => (
      <li key={i.key} className="flex items-center justify-between gap-3 border-t border-wt-line py-2.5 text-[15px]">
        <span className="flex items-center gap-2">{i.label}<SeenFrame item={i} /></span>
        <span className="font-bold tabular">{i.amount == null ? "To be priced" : i.amount < 0 ? `-${money(-i.amount)}` : money(i.amount)}</span>
      </li>
    ))}
  </ul>
);

export const QuoteScreen = ({ data, onTalk, onSign, busy }) => {
  const [name, setName] = useState("");
  const q = data.quote;
  return (
    <PortalShell testId="quote-screen">
      <PortalHeader contractor={data.contractor.name} />
      <h1 className="mt-4 font-display text-[30px] font-bold leading-tight text-wt-ink">Your quote is ready, {data.lead.first_name}.</h1>
      <Steps active={0} />
      <section className="mt-4 rounded-2xl border border-wt-line bg-white p-4">
        <div className="flex items-baseline justify-between gap-2">
          <span className="text-[15px] font-semibold text-wt-muted">Estimated total, v{q.version}</span>
          <span className="text-[14px] text-wt-muted tabular">{range(q)}</span>
        </div>
        <p data-testid="quote-total" className="font-display text-[40px] font-bold leading-tight text-wt-ink tabular">{money(q.total)}</p>
        <LineItems quote={q} />
        {q.if_not && (
          <p data-testid="quote-if-not" className="mt-2 rounded-lg bg-wt-soft px-3 py-2 text-[14px] font-semibold text-wt-accent">
            {q.if_not.say} That would make it {money(q.if_not.total)}.
          </p>
        )}
        <button data-testid="talk-to-change-btn" onClick={onTalk}
          className="mt-2 flex min-h-[48px] w-full items-center justify-center gap-2 rounded-xl border border-wt-line text-[16px] font-semibold text-wt-ink hover:border-wt-ink/30">
          <Mic className="h-4 w-4" /> Talk to change this
        </button>
        <QuotePdfLink className="mt-2" />
      </section>
      <section data-testid="contract-summary" className="mt-4 rounded-2xl border border-wt-line bg-white p-4">
        <h2 className="mb-2 text-[17px] font-bold text-wt-ink">Contract summary</h2>
        <Row label="Parties" value={`${data.lead.name} and ${data.contractor.name}`} />
        <Row label="Scope" value={`${data.lead.ask}, as listed`} />
        <Row label="Deposit after signing" value={`${q.deposit_pct}%, ${money(q.deposit_amount)}`} strong />
        <p className="mt-1 text-[13px] text-wt-muted">The full contract opens next. Final price is confirmed by {data.contractor.name.split(" ")[0]} after a site check.</p>
      </section>
      <label className="mt-5 block text-[15px] font-medium text-wt-ink" htmlFor="sign-name">Type your full name to sign</label>
      <input id="sign-name" data-testid="sign-name-input" value={name} onChange={(e) => setName(e.target.value)} placeholder={data.lead.name}
        className="mt-2 h-14 w-full rounded-2xl border border-wt-line bg-white px-4 text-lg italic focus:border-wt-accent focus:outline-none" />
      <PrimaryButton data-testid="sign-contract-btn" className="mt-3" disabled={name.trim().length < 2 || busy} onClick={() => onSign(name.trim())}>
        Sign contract
      </PrimaryButton>
      <p className="mt-3 text-center text-[13px] text-wt-muted">After you sign, we text you a secure link for the {q.deposit_pct}% deposit.</p>
    </PortalShell>
  );
};
