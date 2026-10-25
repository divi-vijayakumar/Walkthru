import { Loader2 } from "lucide-react";

export const inputCls = "mt-1 h-11 w-full rounded-lg border border-wt-line bg-white px-3 text-[15px] font-normal text-wt-ink focus:border-wt-accent focus:outline-none";

export const Field = ({ label, className = "", children }) => (
  <label className={`block text-[13px] font-semibold text-wt-muted ${className}`}>{label}{children}</label>
);

export const TextField = ({ label, value, onChange, testId, area, ...rest }) => (
  <Field label={label}>
    {area ? (
      <textarea data-testid={testId} value={value ?? ""} rows={2} onChange={(e) => onChange(e.target.value)} {...rest}
        className="mt-1 w-full rounded-lg border border-wt-line bg-white p-3 text-[15px] font-normal text-wt-ink focus:border-wt-accent focus:outline-none" />
    ) : (
      <input data-testid={testId} value={value ?? ""} onChange={(e) => onChange(e.target.value)} className={inputCls} {...rest} />
    )}
  </Field>
);

export const MoneyInput = ({ value, onChange, testId, label }) => (
  <Field label={label}>
    <div className="relative">
      <span className="pointer-events-none absolute left-3 top-1/2 mt-0.5 -translate-y-1/2 text-wt-muted">$</span>
      <input data-testid={testId} type="number" min="0" step="1" value={value} onChange={(e) => onChange(e.target.value)} className={`${inputCls} pl-7 tabular`} />
    </div>
  </Field>
);

export const SaveButton = ({ testId, disabled, busy, onClick, children = "Save" }) => (
  <button data-testid={testId} onClick={onClick} disabled={disabled || busy}
    className="mt-3 inline-flex min-h-[44px] items-center gap-2 rounded-lg bg-wt-accent px-5 text-sm font-bold text-white transition-opacity duration-150 hover:opacity-90 disabled:opacity-50">
    {busy && <Loader2 className="h-4 w-4 animate-spin" />}{children}
  </button>
);

export const isAmount = (v) => v !== "" && v != null && Number.isFinite(Number(v)) && Number(v) >= 0;
