import { useState } from "react";
import { Field, SaveButton, TextField, inputCls } from "@/dashboard/settings/fields";

export const PRIORITY = [["", "Automatic (asks if it moves the price $1,000 or more)"], ["1", "Always ask before giving a price"], ["2", "Never hold up the price"]];
const LADDER = { camera: "camera looks", show: "asks to see it", ask: "asks", measure: "measures", assume: "assumes" };
export const ladderText = (l) => `Alex ${l.map((s) => LADDER[s] || s).join(", then ")}`;

export const FactForm = ({ doc, onSave }) => {
  const [f, setF] = useState({ label: doc.label, question: doc.question, show: doc.show, default: doc.default ?? "", priority: doc.priority == null ? "" : String(doc.priority) });
  const [busy, setBusy] = useState(false);
  const set = (k) => (v) => setF((x) => ({ ...x, [k]: v }));
  const id = doc.fact_id;
  const save = async () => {
    setBusy(true);
    await onSave({ ...doc, label: f.label.trim(), question: f.question.trim(), show: f.show.trim(), default: f.default,
      priority: f.priority === "" ? null : Number(f.priority) });
    setBusy(false);
  };
  return (
    <div className="mt-3 grid gap-3 sm:grid-cols-2">
      <TextField label="What it's called" value={f.label} onChange={set("label")} testId={`fact-label-${id}`} maxLength={80} />
      <Field label="Answer if nobody knows">
        {doc.options?.length ? (
          <select data-testid={`fact-default-${id}`} value={f.default} onChange={(e) => set("default")(e.target.value)} className={inputCls}>
            {doc.options.map((o) => <option key={o} value={o}>{o}</option>)}
          </select>
        ) : (
          <input data-testid={`fact-default-${id}`} value={f.default} onChange={(e) => set("default")(e.target.value)} className={inputCls} />
        )}
      </Field>
      <TextField area className="sm:col-span-2" label="How Alex asks" value={f.question} onChange={set("question")} testId={`fact-question-${id}`} maxLength={240} />
      <TextField area label="What Alex asks to see on camera" value={f.show} onChange={set("show")} testId={`fact-show-${id}`} maxLength={240} />
      <Field label="Before giving a price">
        <select data-testid={`fact-priority-${id}`} value={f.priority} onChange={(e) => set("priority")(e.target.value)} className={inputCls}>
          {PRIORITY.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
        </select>
      </Field>
      <div className="sm:col-span-2"><SaveButton testId={`fact-save-${id}`} disabled={f.label.trim().length < 2} busy={busy} onClick={save} /></div>
    </div>
  );
};
