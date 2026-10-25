import { useEffect, useState } from "react";
import { toast } from "sonner";
import { api, errorText } from "@/shared/api";
import { SaveButton, TextField } from "@/dashboard/settings/fields";

const FIELDS = [["name", "Company name"], ["agent_name", "Assistant's name"], ["phone", "Phone"], ["email", "Email (shown on quote PDFs)"],
  ["address", "Address (shown on quote PDFs)"], ["min_margin_pct", "Lowest margin Alex may go to (%)", "number"],
  ["max_discount_pct", "Biggest discount Alex may give (%)", "number"]];

export const CompanyForm = () => {
  const [f, setF] = useState(null);
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    api.get("/dashboard").then((r) => setF(Object.fromEntries(FIELDS.map(([k]) => [k, r.data.contractor[k] ?? ""]))));
  }, []);
  if (!f) return <p className="px-4 py-6 text-sm text-wt-muted">Loading...</p>;
  const save = async () => {
    setBusy(true);
    try {
      await api.put("/contractor/settings", { ...f, min_margin_pct: Number(f.min_margin_pct), max_discount_pct: Number(f.max_discount_pct) });
      toast.success("Company settings saved");
    } catch (e) {
      const d = e?.response?.data?.detail;
      toast.error(Array.isArray(d) ? "Check the fields: names need 2+ letters, margin 0-60%, discount 0-30%" : errorText(e));
    } finally {
      setBusy(false);
    }
  };
  return (
    <div data-testid="company-form" className="grid gap-3 p-4 sm:grid-cols-2">
      {FIELDS.map(([k, label, t]) => (
        <TextField key={k} label={label} value={f[k]} type={t || "text"} min={t ? 0 : undefined} testId={`company-${k}`}
          onChange={(v) => setF((x) => ({ ...x, [k]: v }))} />
      ))}
      <p className="text-[13px] text-wt-muted sm:col-span-2">The deposit is fixed at 5% of the quote.</p>
      <div className="sm:col-span-2"><SaveButton testId="company-save" busy={busy} onClick={save} /></div>
    </div>
  );
};
