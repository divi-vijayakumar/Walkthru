import { useState } from "react";
import { MoneyInput, SaveButton, TextField, isAmount } from "@/dashboard/settings/fields";

const TIERS = ["Refresh", "Standard", "Premium"];

export const condition = (p, facts) => {
  const parts = Object.entries(p.when || {}).map(([k, v]) => `${facts[k]?.label || k}: ${v.join(" or ")}`);
  return [parts.length ? `When ${parts.join(", ")}` : "Always", p.qty ? `per ${facts[p.qty]?.label || p.qty}` : ""].filter(Boolean).join(" · ");
};

const PriceRow = ({ p, i, facts, taskId, onChange }) => (
  <div data-testid={`price-row-${taskId}-${i}`} className="rounded-xl border border-wt-line bg-wt-ground/60 p-3">
    <p className="text-[14px] font-bold text-wt-ink first-letter:uppercase">{p.label || "Price"}</p>
    <p className="text-[12px] text-wt-muted">{condition(p, facts)}</p>
    {p.tiers ? (
      <div className="mt-1 grid grid-cols-3 gap-2">
        {p.tiers.map((t, k) => (
          <MoneyInput key={TIERS[k]} label={TIERS[k]} value={t} testId={`price-${taskId}-${i}-tier-${k}`}
            onChange={(v) => onChange({ ...p, tiers: p.tiers.map((x, j) => (j === k ? v : x)) })} />
        ))}
      </div>
    ) : (
      <div className="mt-1 max-w-[200px]"><MoneyInput label="Amount" value={p.amount} testId={`price-${taskId}-${i}-amount`} onChange={(v) => onChange({ ...p, amount: v })} /></div>
    )}
  </div>
);

export const TaskForm = ({ doc, facts, onSave }) => {
  const [label, setLabel] = useState(doc.label);
  const [price, setPrice] = useState(doc.price);
  const [busy, setBusy] = useState(false);
  const valid = label.trim().length > 1 && price.every((p) => (p.tiers || [p.amount]).every(isAmount));
  const save = async () => {
    setBusy(true);
    const clean = price.map((p) => (p.tiers ? { ...p, tiers: p.tiers.map(Number) } : { ...p, amount: Number(p.amount) }));
    await onSave({ ...doc, label: label.trim(), price: clean });
    setBusy(false);
  };
  return (
    <div className="mt-3 space-y-3">
      <TextField label="Name on the quote" value={label} onChange={setLabel} testId={`task-label-${doc.task_id}`} maxLength={80} />
      {price.map((p, i) => (
        <PriceRow key={i} p={p} i={i} facts={facts} taskId={doc.task_id} onChange={(np) => setPrice((ps) => ps.map((x, j) => (j === i ? np : x)))} />
      ))}
      <SaveButton testId={`task-save-${doc.task_id}`} disabled={!valid} busy={busy} onClick={save} />
    </div>
  );
};
