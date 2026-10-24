export const ALL_FILTER = "all";

export const FilterSelect = ({ id, label, value, onChange, options }) => (
  <label className="flex items-center gap-2 text-sm text-wt-muted">
    {label}
    <select
      data-testid={`filter-${id}`}
      value={value}
      onChange={(e) => onChange(e.target.value)}
      className="h-10 min-w-[120px] rounded-lg border border-wt-line bg-white px-2.5 text-sm text-wt-ink focus:border-wt-accent focus:outline-none focus:ring-2 focus:ring-wt-soft"
    >
      <option value={ALL_FILTER}>All</option>
      {options.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
    </select>
  </label>
);
