import { useCallback, useEffect, useMemo, useState } from "react";
import { api } from "@/shared/api";
import { money } from "@/shared/format";
import { when } from "@/dashboard/CallDetail";
import { Badge, Chips, PageShell, SampleTag, Stat } from "@/dashboard/PageShell";
import { RecordPaymentDialog } from "@/dashboard/RecordPaymentDialog";

const FILTERS = [["all", "All"], ["pending", "Due"], ["paid", "Paid"], ["void", "Void"]];
const STATUS = { pending: ["Due", "accent"], paid: ["Paid", "green"], void: ["Void", "muted"] };
const METHOD = { stripe: "Card (Stripe)", simulated: "Test payment", cash: "Cash", check: "Check", other: "Other" };

const PaymentRow = ({ p, onRecord }) => {
  const [label, tone] = STATUS[p.status] || [p.status, "muted"];
  const failed = p.status === "pending" && ["failed", "expired"].includes(p.checkout);
  return (
    <tr data-testid={`payment-row-${p.id}`} className="border-t border-wt-line">
      <td className="px-4 py-3"><p className="font-bold text-wt-ink">{p.lead_name}<SampleTag show={p.sample} /></p><p className="text-[13px] text-wt-muted">{p.ask}</p></td>
      <td className="px-4 py-3 font-bold tabular">{money(p.amount)}<p className="text-[12px] font-normal text-wt-muted">of {money(p.project_total) || "n/a"}</p></td>
      <td className="px-4 py-3"><Badge tone={tone} testId={`payment-status-${p.id}`}>{label}</Badge>{failed && <p className="mt-1 text-[12px] text-wt-accent">Last checkout {p.checkout}</p>}</td>
      <td className="px-4 py-3">{METHOD[p.method] || ""}{p.reference && p.method !== "stripe" && <p className="text-[12px] text-wt-muted">{p.reference}</p>}</td>
      <td className="px-4 py-3">{when(p.created_at)}</td>
      <td className="px-4 py-3">{when(p.paid_at)}</td>
      <td className="px-4 py-3 text-right">
        {p.can_record && (
          <button data-testid={`record-payment-btn-${p.id}`} onClick={() => onRecord(p)}
            className="min-h-[40px] whitespace-nowrap rounded-lg border border-wt-line px-3 text-[13px] font-bold transition-colors duration-150 hover:border-wt-ink/30">Record payment</button>
        )}
      </td>
    </tr>
  );
};

export default function PaymentsPage() {
  const [data, setData] = useState(null);
  const [filter, setFilter] = useState("all");
  const [recording, setRecording] = useState(null);
  const load = useCallback(() => api.get("/payments").then((r) => setData(r.data)).catch(() => setData({ payments: [], totals: {} })), []);
  useEffect(() => { document.title = "Payments · Walkthru"; load(); }, [load]);
  const rows = useMemo(() => (data?.payments || []).filter((p) => filter === "all" || p.status === filter), [data, filter]);
  const t = data?.totals || {};
  return (
    <PageShell testId="payments-page" title="Payments" subtitle="Deposits asked for after signing. Card payments come in through Stripe; record cash or checks here.">
      <div className="mt-6 grid gap-3 sm:grid-cols-3">
        <Stat testId="payments-stat-due" label="Deposits due" value={money(t.due || 0)} note={`${t.due_count || 0} waiting`} />
        <Stat testId="payments-stat-30d" label="Paid, last 30 days" value={money(t.paid_30d || 0)} />
        <Stat testId="payments-stat-paid" label="Paid, all time" value={money(t.paid || 0)} note={`${t.paid_count || 0} deposit${t.paid_count === 1 ? "" : "s"}`} />
      </div>
      <div className="mt-5"><Chips prefix="payments-filter" options={FILTERS} value={filter} onChange={setFilter} /></div>
      <div className="mt-4 overflow-x-auto rounded-2xl border border-wt-line bg-white">
        <table className="w-full min-w-[760px] text-left text-[14px]">
          <thead className="text-[13px] text-wt-muted"><tr>{["Lead", "Deposit", "Status", "Method", "Requested", "Paid on", ""].map((h) => <th key={h} className="px-4 py-3 font-semibold">{h}</th>)}</tr></thead>
          <tbody>
            {rows.map((p) => <PaymentRow key={p.id} p={p} onRecord={setRecording} />)}
            {data && rows.length === 0 && <tr><td colSpan={7} data-testid="payments-empty" className="px-4 py-6 text-wt-muted">No deposits here yet.</td></tr>}
          </tbody>
        </table>
      </div>
      {recording && <RecordPaymentDialog payment={recording} onClose={() => setRecording(null)} onDone={() => { setRecording(null); load(); }} />}
    </PageShell>
  );
}
