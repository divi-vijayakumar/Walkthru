import { useEffect, useState } from "react";
import { Download, Loader2 } from "lucide-react";
import { toast } from "sonner";
import { api } from "@/shared/api";
import { money, range } from "@/shared/format";
import { when } from "@/dashboard/CallDetail";
import { Badge } from "@/dashboard/PageShell";
import { CustomLine } from "@/dashboard/CustomLine";
import { IfNot } from "@/dashboard/NeedsPrice";

export const QUOTE_STATUS = { live: ["In call", "teal"], sent: ["Sent", "accent"], accepted: ["Accepted", "green"], recalled: ["Recalled", "muted"] };

export const QuoteStatus = ({ status, testId }) => {
  const [label, tone] = QUOTE_STATUS[status] || [status, "muted"];
  return <Badge tone={tone} testId={testId}>{label}</Badge>;
};

const downloadPdf = async (q, setBusy) => {
  setBusy(true);
  try {
    const r = await api.get(`/quotes/${q.id}/pdf`, { responseType: "blob" });
    const url = URL.createObjectURL(r.data);
    const a = Object.assign(document.createElement("a"), { href: url, download: `${q.lead.name} quote v${q.version}.pdf` });
    a.click();
    setTimeout(() => URL.revokeObjectURL(url), 2000);
  } catch {
    toast.error("Couldn't make the PDF");
  } finally {
    setBusy(false);
  }
};

const Versions = ({ q, onPick }) => (
  <div className="mt-5">
    <h3 className="text-[13px] font-bold uppercase tracking-wide text-wt-muted">Versions</h3>
    <ul className="mt-1">
      {q.versions.map((v) => (
        <li key={v.id}>
          <button data-testid={`quote-version-${v.version}`} onClick={() => onPick(v.id)}
            className={`flex min-h-[44px] w-full items-center justify-between gap-2 border-t border-wt-line text-left text-[14px] ${v.id === q.id ? "font-bold" : ""}`}>
            <span>v{v.version} · {when(v.created_at)}</span>
            <span className="flex items-center gap-2 tabular">{money(v.total)} <QuoteStatus status={v.status} /></span>
          </button>
        </li>
      ))}
    </ul>
  </div>
);

export const QuoteDetail = ({ quoteId, onPick, onChanged }) => {
  const [q, setQ] = useState(null);
  const [busy, setBusy] = useState(false);
  useEffect(() => { api.get(`/quotes/${quoteId}`).then((r) => setQ(r.data)).catch(() => toast.error("Couldn't load the quote")); }, [quoteId]);
  if (!q) return <p className="text-[14px] text-wt-muted">Loading...</p>;
  return (
    <div data-testid="quote-detail">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-[17px] font-bold text-wt-ink">{q.lead.name}</p>
          <p className="text-[13px] text-wt-muted">{q.lead.ask} · v{q.version} · {when(q.created_at)}</p>
        </div>
        <QuoteStatus status={q.status} testId="quote-detail-status" />
      </div>
      <p data-testid="quote-detail-total" className="mt-3 font-display text-[34px] font-bold leading-tight tabular">{money(q.total)}</p>
      <p className="text-[13px] text-wt-muted tabular">{range(q)} · deposit {q.deposit_pct}%, {money(q.deposit_amount)}{q.margin_pct != null ? ` · margin ${q.margin_pct}%` : ""}</p>
      <ul className="mt-3">
        {q.line_items.map((i) => (i.custom ? (
          <CustomLine key={i.key} leadId={q.lead_id} line={i} onPriced={(r) => { onChanged?.(); if (r.quote_id) onPick(r.quote_id); }} />
        ) : (
          <li key={i.key} className="flex justify-between gap-3 border-t border-wt-line py-2 text-[14px]">
            <span>{i.label}</span><span className="font-semibold tabular">{i.amount == null ? "To be priced" : i.amount < 0 ? `-${money(-i.amount)}` : money(i.amount)}</span>
          </li>
        )))}
      </ul>
      <IfNot ifNot={q.if_not} className="mt-2" />
      {q.assumptions?.length > 0 && (
        <ul data-testid="quote-detail-assumptions" className="mt-3 list-disc pl-5 text-[13px] text-wt-muted">{q.assumptions.map((a) => <li key={a}>{a}</li>)}</ul>
      )}
      <button data-testid="quote-download-pdf-btn" onClick={() => downloadPdf(q, setBusy)} disabled={busy}
        className="mt-4 flex min-h-[44px] w-full items-center justify-center gap-2 rounded-xl bg-wt-accent text-[15px] font-bold text-white transition-opacity duration-150 hover:opacity-90 disabled:opacity-60">
        {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Download className="h-4 w-4" />} Download PDF
      </button>
      <Versions q={q} onPick={onPick} />
    </div>
  );
};
