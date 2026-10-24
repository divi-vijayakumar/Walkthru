import { Check, House } from "lucide-react";

export const PortalHeader = ({ contractor, logo = false }) => (
  <div className="flex items-center justify-between">
    <div className="flex items-center gap-2">
      {logo && (
        <span className="grid h-8 w-8 place-items-center rounded-lg bg-wt-accent text-white">
          <House className="h-4 w-4" strokeWidth={2.4} />
        </span>
      )}
      <span className="font-display text-lg font-bold text-wt-ink">Walkthru</span>
    </div>
    <span className="text-sm font-semibold text-wt-muted">{contractor}</span>
  </div>
);

export const PortalShell = ({ children, testId }) => (
  <div data-testid={testId} className="min-h-screen bg-wt-ground">
    <div className="mx-auto flex min-h-screen max-w-[420px] flex-col px-5 pb-6 pt-5">{children}</div>
  </div>
);

const STEPS = ["Quote", "Contract", "Deposit"];

export const Steps = ({ active }) => (
  <div data-testid="progress-steps" className="mt-3 flex items-center gap-2">
    {STEPS.map((s, i) => {
      const cls = i < active ? "bg-[#D9F0EB] text-[#0B5F55]" : i === active ? "bg-wt-teal text-white"
        : i === active + 1 ? "bg-wt-soft text-wt-accentDark" : "bg-[#E9ECF1] text-wt-muted";
      return (
        <div key={s} className="flex items-center gap-2">
          {i > 0 && <span className="text-wt-muted">›</span>}
          <span className={`inline-flex items-center gap-1 rounded-full px-3 py-1.5 text-sm font-bold ${cls}`}>
            {i < active ? <Check className="h-3.5 w-3.5" strokeWidth={3} /> : `${i + 1}`} {s}
          </span>
        </div>
      );
    })}
  </div>
);

export const PrimaryButton = ({ children, className = "", ...props }) => (
  <button {...props}
    className={`flex min-h-[56px] w-full items-center justify-center gap-2 rounded-2xl bg-wt-accent px-5 text-lg font-bold text-white transition-colors hover:bg-wt-accentDark disabled:opacity-50 ${className}`}>
    {children}
  </button>
);

export const Row = ({ label, value, strong }) => (
  <div className="flex items-center justify-between gap-4 border-t border-wt-line py-2.5 text-[15px]">
    <span className="text-wt-ink">{label}</span>
    <span className={`text-right font-bold ${strong ? "text-wt-accentDark" : "text-wt-ink"}`}>{value}</span>
  </div>
);
