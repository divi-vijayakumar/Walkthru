import { useState } from "react";
import { SaveButton, TextField, isAmount } from "@/dashboard/settings/fields";

const FIELDS = {
  rule: [["note", "What this rule is for", "area"]],
  driver: [["name", "Name"], ["how", "How Alex finds out", "area"], ["effect", "Effect on the price", "area"]],
  measure_method: [["name", "Name"], ["how", "How Alex asks", "area"], ["best_for", "Best for"], ["uncertainty_pct", "Uncertainty added to the range (%)", "number"]],
};
export const KIND = { rule: "Adds work", driver: "Price driver", measure_method: "Way to measure" };

export const ruleText = (d, tasks, facts) => {
  if (d.kind !== "rule") return d.how || "";
  const names = (ids) => ids.map((t) => tasks[t]?.label || t).join(" + ");
  const fs = Object.entries(d.facts || {}).map(([k, v]) => `${facts[k]?.label || k} is ${v.join(" or ")}`);
  return [`Adds "${tasks[d.add]?.label || d.add}"`, d.has.length && `when the job has ${names(d.has)}`,
    d.lacks.length && `and no ${names(d.lacks)}`, fs.length && `(${fs.join(", ")})`].filter(Boolean).join(" ");
};

export const RuleForm = ({ doc, tasks, facts, onSave }) => {
  const fields = FIELDS[doc.kind] || [];
  const [f, setF] = useState(Object.fromEntries(fields.map(([k]) => [k, doc[k] ?? ""])));
  const [busy, setBusy] = useState(false);
  const valid = fields.every(([k, , t]) => (t === "number" ? isAmount(f[k]) : k !== "name" || String(f[k]).trim().length > 1));
  const save = async () => {
    setBusy(true);
    const clean = Object.fromEntries(fields.map(([k, , t]) => [k, t === "number" ? Number(f[k]) : String(f[k]).trim()]));
    await onSave({ ...doc, ...clean });
    setBusy(false);
  };
  return (
    <div className="mt-3 space-y-3">
      {doc.kind === "rule" && <p data-testid={`rule-logic-${doc.rule_id}`} className="rounded-lg bg-wt-ground px-3 py-2 text-[13px] text-wt-ink">{ruleText(doc, tasks, facts)}</p>}
      {fields.map(([k, label, t]) => (
        <TextField key={k} label={label} value={f[k]} area={t === "area"} type={t === "number" ? "number" : "text"} min={t === "number" ? 0 : undefined}
          onChange={(v) => setF((x) => ({ ...x, [k]: v }))} testId={`rule-${k}-${doc.rule_id}`} />
      ))}
      <SaveButton testId={`rule-save-${doc.rule_id}`} disabled={!valid} busy={busy} onClick={save} />
    </div>
  );
};
