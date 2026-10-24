import { useState } from "react";
import { CheckCircle2, Loader2 } from "lucide-react";
import { money } from "@/shared/format";
import { PortalHeader, PortalShell, PrimaryButton, Row, Steps } from "@/portal/PortalShell";
import { LineItems } from "@/portal/QuoteScreen";

export const ContractScreen = ({ data, initialName, onSign, busy }) => {
  const [name, setName] = useState(initialName || "");
  const q = data.quote;
  const c = data.contractor.name;
  return (
    <PortalShell testId="contract-screen">
      <PortalHeader contractor={c} />
      <h1 className="mt-4 font-display text-[30px] font-bold leading-tight">Review and sign</h1>
      <Steps active={1} />
      <section className="mt-4 rounded-2xl border border-wt-line bg-white p-4 text-[14px] leading-relaxed text-wt-ink">
        <h2 className="text-[17px] font-bold">Home improvement agreement</h2>
        <p className="mt-2">This agreement is between {data.lead.name} (homeowner) and {c} (contractor) for the {data.lead.ask.toLowerCase()} described below, based on quote version {q.version}.</p>
        <LineItems quote={q} />
        <Row label="Contract price" value={money(q.total)} />
        <Row label={`Deposit due at signing (${q.deposit_pct}%)`} value={money(q.deposit_amount)} strong />
        <p className="mt-2">{c} confirms the final price after a site check. Any change above the quoted range needs the homeowner's written approval. The remaining balance is billed on milestones agreed at the site check.</p>
        <p className="mt-2 text-[12px] text-wt-muted">Demo agreement for illustration only.</p>
      </section>
      <label className="mt-5 block text-[15px] font-medium" htmlFor="confirm-name">Your full name</label>
      <input id="confirm-name" data-testid="confirm-name-input" value={name} onChange={(e) => setName(e.target.value)}
        className="mt-2 h-14 w-full rounded-2xl border border-wt-line bg-white px-4 text-lg italic focus:border-wt-accent focus:outline-none" />
      <PrimaryButton data-testid="confirm-sign-btn" className="mt-3" disabled={name.trim().length < 2 || busy} onClick={() => onSign(name.trim())}>
        {busy ? <Loader2 className="h-5 w-5 animate-spin" /> : null} Sign and continue
      </PrimaryButton>
    </PortalShell>
  );
};

export const DepositScreen = ({ data, onPay, busy }) => (
  <PortalShell testId="deposit-screen">
    <PortalHeader contractor={data.contractor.name} />
    <h1 className="mt-4 font-display text-[30px] font-bold leading-tight">Contract signed. One last step.</h1>
    <Steps active={2} />
    <section className="mt-4 rounded-2xl border border-wt-line bg-white p-5">
      <p className="text-[15px] font-semibold text-wt-muted">Deposit due</p>
      <p data-testid="deposit-amount" className="font-display text-[40px] font-bold leading-tight tabular">{money(data.payment?.amount)}</p>
      <Row label="Project total" value={money(data.quote?.total)} />
      <Row label="Deposit" value={`${data.quote?.deposit_pct}% of total`} />
      <p className="mt-2 text-[13px] text-wt-muted">Simulated payment for this demo. No card is needed and no money moves.</p>
    </section>
    <div className="mt-auto pt-8">
      <PrimaryButton data-testid="pay-deposit-btn" onClick={onPay} disabled={busy}>
        {busy ? <><Loader2 className="h-5 w-5 animate-spin" /> Processing</> : `Pay deposit ${money(data.payment?.amount)}`}
      </PrimaryButton>
    </div>
  </PortalShell>
);

export const DoneScreen = ({ data }) => (
  <PortalShell testId="done-screen">
    <PortalHeader contractor={data.contractor.name} />
    <div className="mt-14 flex flex-col items-center text-center">
      <CheckCircle2 className="h-16 w-16 text-wt-teal" strokeWidth={1.8} />
      <h1 className="mt-4 font-display text-[30px] font-bold leading-tight">You're booked, {data.lead.first_name}.</h1>
      <p className="mt-2 text-[16px] text-wt-muted">Deposit received. {data.contractor.name} will text you to schedule the site check.</p>
    </div>
    <section className="mt-8 rounded-2xl border border-wt-line bg-white px-4 pb-1 pt-2">
      <Row label="Deposit paid" value={money(data.payment?.amount)} />
      <Row label="Project total" value={money(data.quote?.total)} />
      <Row label="Questions" value={data.contractor.phone} />
    </section>
  </PortalShell>
);

export const FallbackScreen = ({ data }) => (
  <PortalShell testId="fallback-screen">
    <PortalHeader contractor={data.contractor.name} />
    <div className="mt-14">
      <h1 data-testid="fallback-title" className="font-display text-[30px] font-bold leading-tight">
        Thanks, {data.lead.first_name}. We have what we need and your quote is on the way shortly.
      </h1>
      <p data-testid="fallback-contact" className="mt-4 text-[16px] text-wt-muted">
        We'll text it to {data.lead.phone} as soon as {data.contractor.name} has priced it.
      </p>
      <p className="mt-2 text-[14px] text-wt-muted">You can close this page. This link will show your quote when it's ready.</p>
    </div>
  </PortalShell>
);

export const ClosedScreen = ({ data }) => (
  <PortalShell testId="closed-screen">
    <PortalHeader contractor={data.contractor.name} />
    <h1 className="mt-14 font-display text-[28px] font-bold leading-tight">This project link is no longer active.</h1>
    <p className="mt-3 text-[16px] text-wt-muted">Call {data.contractor.name} at {data.contractor.phone} to pick it back up.</p>
  </PortalShell>
);
