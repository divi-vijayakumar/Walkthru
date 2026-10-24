import { STATUS } from "@/shared/status";

export const StatusPill = ({ status, flash, testId }) => {
  const s = STATUS[status] || STATUS.new;
  return (
    <span
      data-testid={testId}
      className={`inline-flex items-center gap-1.5 whitespace-nowrap rounded-full px-2.5 py-1 text-[13px] font-semibold ${flash ? "pill-pop" : ""}`}
      style={{ backgroundColor: s.bg, color: s.fg }}
    >
      {status === "walkthru_initiated" && <span className="h-2 w-2 animate-pulse rounded-full bg-wt-accent" />}
      {s.label}
    </span>
  );
};
