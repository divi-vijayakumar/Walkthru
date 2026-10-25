import { useCallback, useEffect, useState } from "react";
import { api } from "@/shared/api";
import { money } from "@/shared/format";
import { CustomLine } from "@/dashboard/CustomLine";

export const IfNot = ({ ifNot, className = "" }) => (ifNot ? (
  <p data-testid="quote-if-not" className={`rounded-lg bg-wt-soft px-3 py-2 text-[13px] font-semibold text-wt-accent ${className}`}>
    {ifNot.say} That would make it {money(ifNot.total)}.
  </p>
) : null);

export const NeedsPrice = ({ leadId, onChanged }) => {
  const [items, setItems] = useState([]);
  const load = useCallback(() => api.get(`/itemizer/${leadId}/custom`).then((r) => setItems(r.data.items)).catch(() => setItems([])), [leadId]);
  useEffect(() => { load(); }, [load]);
  if (!items.length) return null;
  return (
    <section data-testid="needs-price" className="mt-5 rounded-xl border border-wt-accent/40 p-3.5">
      <p className="text-sm font-bold text-wt-ink">Needs your price</p>
      <p className="text-[12px] text-wt-muted">Work Alex couldn't price. Your price is saved to the rate card for the next homeowner.</p>
      <ul className="mt-1">{items.map((i) => <CustomLine key={i.item_id} leadId={leadId} line={{ ...i, details: i }} onPriced={() => { load(); onChanged?.(); }} />)}</ul>
    </section>
  );
};
