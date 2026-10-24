export const AgentSwitch = ({ enabled, onToggle }) => (
  <div className="flex items-center gap-4 rounded-xl border border-wt-line bg-white px-4 py-3">
    <div>
      <p className="text-[15px] font-bold text-wt-ink">Agentic lead management</p>
      <p className="text-[13px] text-wt-muted">Texts new leads and runs the walkthrough</p>
    </div>
    <button
      role="switch"
      aria-checked={enabled}
      aria-label="Agentic lead management"
      data-testid="agent-switch"
      onClick={() => onToggle(!enabled)}
      className="flex min-h-[44px] shrink-0 items-center gap-2"
    >
      <span className={`relative block h-7 w-12 shrink-0 rounded-full transition-colors duration-200 ${enabled ? "bg-wt-teal" : "bg-[#C9CFD8]"}`}>
        <span className={`absolute left-0 top-0.5 h-6 w-6 rounded-full bg-white shadow transition-transform duration-200 ${enabled ? "translate-x-[22px]" : "translate-x-0.5"}`} />
      </span>
      <span data-testid="agent-switch-label" className={`w-8 shrink-0 text-left text-sm font-bold ${enabled ? "text-wt-teal" : "text-wt-muted"}`}>
        {enabled ? "On" : "Off"}
      </span>
    </button>
  </div>
);

export const DashboardHeader = ({ contractor, onToggle }) => (
  <div className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
    <div>
      <div className="flex items-center gap-3">
        <h1 className="font-display text-4xl font-bold tracking-tight text-wt-ink">Leads</h1>
        <span data-testid="sample-data-chip" className="rounded-md bg-[#E9ECF1] px-2 py-1 text-xs font-semibold text-wt-muted">
          Sample data
        </span>
      </div>
      <p className="mt-1.5 text-[15px] text-wt-muted">
        From first text to deposit, the agent runs each lead. You watch and step in when needed.
      </p>
    </div>
    {contractor && <AgentSwitch enabled={contractor.agent_enabled} onToggle={onToggle} />}
  </div>
);
