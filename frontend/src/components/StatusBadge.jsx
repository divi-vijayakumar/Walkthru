import { STATUSES } from "@/lib/api";

export const StatusBadge = ({ status, testId }) => {
  const s = STATUSES[status] || STATUSES.new;
  return (
    <span
      data-testid={testId}
      className={`inline-flex items-center gap-1.5 whitespace-nowrap rounded-full border px-2.5 py-0.5 font-mono text-[11px] font-medium uppercase tracking-wider ${s.className}`}
    >
      <span className="h-1.5 w-1.5 rounded-full bg-current" />
      {s.label}
    </span>
  );
};
