import { Sidebar } from "@/dashboard/Sidebar";

export const PageShell = ({ testId, title, subtitle, children }) => (
  <div className="min-h-screen bg-wt-ground lg:flex">
    <Sidebar />
    <main data-testid={testId} className="min-w-0 flex-1 px-4 py-6 sm:px-6 lg:px-8 lg:py-8">
      <h1 className="font-display text-4xl font-bold tracking-tight text-wt-ink">{title}</h1>
      <p className="mt-1.5 text-[15px] text-wt-muted">{subtitle}</p>
      {children}
    </main>
  </div>
);

export const Stat = ({ testId, label, value, note }) => (
  <div data-testid={testId} className="rounded-2xl border border-wt-line bg-white px-4 py-3.5">
    <p className="text-[13px] font-semibold text-wt-muted">{label}</p>
    <p className="mt-0.5 font-display text-[28px] font-bold leading-tight text-wt-ink tabular">{value}</p>
    {note && <p className="text-[12px] text-wt-muted">{note}</p>}
  </div>
);

export const Chips = ({ prefix, options, value, onChange }) => (
  <div className="flex flex-wrap gap-2">
    {options.map(([k, label]) => (
      <button key={k} data-testid={`${prefix}-${k}`} onClick={() => onChange(k)}
        className={`min-h-[40px] rounded-full px-3.5 text-[14px] font-semibold transition-colors duration-150 ${
          value === k ? "bg-wt-ink text-white" : "border border-wt-line bg-white text-wt-ink hover:border-wt-ink/30"}`}>
        {label}
      </button>
    ))}
  </div>
);

export const Badge = ({ tone, children, testId }) => {
  const tones = { teal: "bg-[#CCFBF1] text-wt-teal", accent: "bg-wt-soft text-wt-accent", green: "bg-[#DCFCE7] text-[#166534]",
    muted: "bg-[#EEF1F5] text-wt-muted" };
  return <span data-testid={testId} className={`inline-flex rounded-full px-2.5 py-0.5 text-[12px] font-bold ${tones[tone]}`}>{children}</span>;
};

export const SampleTag = ({ show }) => (show ? <span className="ml-2 text-xs font-semibold text-wt-muted">sample</span> : null);
