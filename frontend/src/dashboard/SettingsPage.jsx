import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { toast } from "sonner";
import { api, errorText } from "@/shared/api";

const TABS = [["tasks", "Tasks and prices", "task_id"], ["facts", "Facts and ladders", "fact_id"], ["rules", "Rules, drivers and measuring", "rule_id"]];

const summary = (tab, d) => {
  if (tab === "tasks") return `${d.room || "any room"} · ${d.price.map((p) => (p.tiers ? p.tiers.join(" / ") : p.amount) + (p.qty ? ` per ${p.qty}` : "")).join(" + ")}`;
  if (tab === "facts") return `${d.scope} · ${d.ladder.join(" > ")} · default ${d.default}`;
  return d.kind === "rule" ? `adds ${d.add} · ${d.note}` : `${d.kind} · ${d.name}`;
};

const Row = ({ tab, idKey, doc, onSaved }) => {
  const [open, setOpen] = useState(false);
  const [text, setText] = useState("");
  const save = async () => {
    try {
      const parsed = JSON.parse(text);
      await api.put(`/kb/${tab}/${doc[idKey]}`, parsed);
      toast.success("Saved");
      setOpen(false);
      onSaved();
    } catch (e) {
      toast.error(e instanceof SyntaxError ? "That isn't valid JSON" : errorText(e));
    }
  };
  return (
    <li data-testid={`kb-row-${doc[idKey]}`} className="border-t border-wt-line px-4 py-3">
      <div className="flex items-center gap-3">
        <div className="min-w-0 flex-1">
          <p className="font-semibold">{doc.label || doc.name || doc[idKey]} <span className="text-xs text-wt-muted">{doc[idKey]}</span></p>
          <p className="truncate text-[13px] text-wt-muted">{summary(tab, doc)}</p>
        </div>
        <button data-testid={`kb-edit-${doc[idKey]}`} onClick={() => { setText(JSON.stringify(doc, null, 2)); setOpen(!open); }}
          className="min-h-[40px] rounded-lg border border-wt-line px-3 text-sm font-bold">{open ? "Close" : "Edit"}</button>
      </div>
      {open && (
        <div className="mt-3">
          <textarea data-testid={`kb-json-${doc[idKey]}`} value={text} onChange={(e) => setText(e.target.value)} rows={14}
            className="w-full rounded-lg border border-wt-line p-3 font-mono text-[12px]" />
          <button data-testid={`kb-save-${doc[idKey]}`} onClick={save} className="mt-2 min-h-[44px] rounded-lg bg-wt-accent px-4 text-sm font-bold text-white">Save</button>
        </div>
      )}
    </li>
  );
};

export default function SettingsPage() {
  const [kb, setKb] = useState(null);
  const [tab, setTab] = useState("tasks");
  const load = useCallback(() => api.get("/kb").then((r) => setKb(r.data)), []);
  useEffect(() => { document.title = "Rate card and settings · Walkthru"; load(); }, [load]);
  const [, label, idKey] = TABS.find((t) => t[0] === tab);
  return (
    <div data-testid="settings-page" className="mx-auto min-h-screen max-w-5xl px-4 py-8">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="font-display text-3xl font-bold">Rate card and settings</h1>
          <p className="text-sm text-wt-muted">The Itemizer's knowledge base. All prices are placeholders until you replace them.</p>
        </div>
        <Link to="/" className="inline-flex min-h-[44px] items-center rounded-lg border border-wt-line bg-white px-3.5 text-sm font-bold">Dashboard</Link>
      </div>
      <div className="mt-6 flex flex-wrap gap-2">
        {TABS.map(([k, l]) => (
          <button key={k} data-testid={`kb-tab-${k}`} onClick={() => setTab(k)}
            className={`min-h-[44px] rounded-lg px-3.5 text-sm font-bold ${tab === k ? "bg-wt-ink text-white" : "border border-wt-line bg-white"}`}>{l}</button>
        ))}
      </div>
      <h2 className="mb-2 mt-6 text-sm font-bold uppercase tracking-wide text-wt-muted">{label}</h2>
      <ul className="overflow-hidden rounded-2xl border border-wt-line bg-white">
        {!kb && <li className="px-4 py-6 text-sm text-wt-muted">Loading...</li>}
        {kb?.[tab].map((d) => <Row key={d[idKey]} tab={tab} idKey={idKey} doc={d} onSaved={load} />)}
      </ul>
    </div>
  );
}
