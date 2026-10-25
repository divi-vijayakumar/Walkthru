import { useCallback, useEffect, useMemo, useState } from "react";
import { toast } from "sonner";
import { api, errorText } from "@/shared/api";
import { money } from "@/shared/format";
import { Chips, PageShell } from "@/dashboard/PageShell";
import { TaskForm } from "@/dashboard/settings/TaskForm";
import { FactForm, PRIORITY, ladderText } from "@/dashboard/settings/FactForm";
import { KIND, RuleForm, ruleText } from "@/dashboard/settings/RuleForm";
import { CompanyForm } from "@/dashboard/settings/CompanyForm";

const TABS = [["tasks", "Prices"], ["facts", "Questions"], ["rules", "Rules"], ["company", "Company"]];
const ID = { tasks: "task_id", facts: "fact_id", rules: "rule_id" };
const ROOM = (r) => (r ? r[0].toUpperCase() + r.slice(1) : "Any room");

const priceText = (d) => d.price.map((p) => (p.tiers ? `${money(p.tiers[0])}-${money(p.tiers[2])}` : money(p.amount))).join(" · ");
const summary = (tab, d, maps) => {
  if (tab === "tasks") return `${ROOM(d.room)} · ${priceText(d)}`;
  if (tab === "facts") return `${ladderText(d.ladder)} · ${PRIORITY.find(([v]) => v === (d.priority == null ? "" : String(d.priority)))[1].split(" (")[0]}`;
  return `${KIND[d.kind] || d.kind} · ${ruleText(d, maps.tasks, maps.facts)}`;
};

const KbRow = ({ tab, doc, maps, onSave }) => {
  const [open, setOpen] = useState(false);
  const id = doc[ID[tab]];
  const save = async (next) => {
    try {
      await api.put(`/kb/${tab}/${id}`, next);
      toast.success("Saved");
      setOpen(false);
      onSave();
    } catch (e) {
      toast.error(errorText(e));
    }
  };
  const Form = { tasks: TaskForm, facts: FactForm, rules: RuleForm }[tab];
  return (
    <li data-testid={`kb-row-${id}`} className="border-t border-wt-line px-4 py-3 first:border-t-0">
      <div className="flex items-center gap-3">
        <div className="min-w-0 flex-1">
          <p className="font-semibold text-wt-ink">{doc.label || doc.name || id}</p>
          <p className="truncate text-[13px] text-wt-muted">{summary(tab, doc, maps)}</p>
        </div>
        <button data-testid={`kb-edit-${id}`} onClick={() => setOpen(!open)}
          className="min-h-[40px] rounded-lg border border-wt-line px-3 text-sm font-bold transition-colors duration-150 hover:border-wt-ink/30">{open ? "Close" : "Edit"}</button>
      </div>
      {open && <Form doc={doc} facts={maps.facts} tasks={maps.tasks} onSave={save} />}
    </li>
  );
};

export default function SettingsPage() {
  const [kb, setKb] = useState(null);
  const [tab, setTab] = useState("tasks");
  const [q, setQ] = useState("");
  const load = useCallback(() => api.get("/kb").then((r) => setKb(r.data)), []);
  useEffect(() => { document.title = "Rate card and settings · Walkthru"; load(); }, [load]);
  const maps = useMemo(() => ({ tasks: Object.fromEntries((kb?.tasks || []).map((t) => [t.task_id, t])),
    facts: Object.fromEntries((kb?.facts || []).map((f) => [f.fact_id, f])) }), [kb]);
  const rows = (kb?.[tab] || []).filter((d) => `${d.label || ""} ${d.name || ""} ${d[ID[tab]]}`.toLowerCase().includes(q.toLowerCase()));
  const groups = tab === "tasks" ? [...new Set(rows.map((d) => d.room || null))].map((r) => [ROOM(r), rows.filter((d) => (d.room || null) === r)]) : [[null, rows]];
  return (
    <PageShell testId="settings-page" title="Rate card and settings" subtitle="What Alex charges, what Alex asks, and the rules behind every quote. All prices are placeholders until you replace them.">
      <div className="mt-6 flex flex-wrap items-center justify-between gap-3">
        <Chips prefix="kb-tab" options={TABS} value={tab} onChange={(t) => { setTab(t); setQ(""); }} />
        {tab !== "company" && (
          <input data-testid="kb-search-input" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search"
            className="h-11 w-full rounded-lg border border-wt-line bg-white px-3 text-[15px] focus:border-wt-accent focus:outline-none sm:w-64" />
        )}
      </div>
      {tab === "company" ? (
        <div className="mt-4 max-w-3xl rounded-2xl border border-wt-line bg-white"><CompanyForm /></div>
      ) : groups.map(([title, docs]) => (
        <section key={title || "all"} className="mt-5 max-w-4xl">
          {title && <h2 className="mb-2 text-sm font-bold uppercase tracking-wide text-wt-muted">{title}</h2>}
          <ul className="overflow-hidden rounded-2xl border border-wt-line bg-white">
            {!kb && <li className="px-4 py-6 text-sm text-wt-muted">Loading...</li>}
            {kb && docs.length === 0 && <li className="px-4 py-6 text-sm text-wt-muted">Nothing matches.</li>}
            {docs.map((d) => <KbRow key={d[ID[tab]]} tab={tab} doc={d} maps={maps} onSave={load} />)}
          </ul>
        </section>
      ))}
    </PageShell>
  );
}
