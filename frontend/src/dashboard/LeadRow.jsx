import { StatusPill } from "@/shared/StatusPill";
import { ACTIVITY, SOURCES } from "@/shared/status";
import { ago, clock, money } from "@/shared/format";

const ACTIONS = { new: "Start agent", invited: "Resend", walkthru_initiated: "Watch" };

export const QuotePendingBadge = ({ due, now }) => {
  const left = (new Date(due).getTime() - now) / 1000;
  const overdue = left < 0;
  return (
    <span
      data-testid="quote-pending-badge"
      className={`inline-flex whitespace-nowrap rounded-md px-2 py-0.5 text-xs font-bold tabular ${
        overdue ? "bg-[#FDE2E2] text-[#B91C1C]" : "bg-[#FDF0D2] text-[#7A4A00]"
      }`}
    >
      {overdue ? `Quote overdue ${clock(-left)}` : `Quote pending ${clock(left)}`}
    </span>
  );
};

const QuoteCell = ({ lead, now }) => {
  if (lead.status === "walkthru_initiated" && lead.live) return <span className="text-wt-muted">Building...</span>;
  if (lead.quote_pending && lead.quote_pending_due_at) return <QuotePendingBadge due={lead.quote_pending_due_at} now={now} />;
  if (lead.quote_total) return <span className="font-bold text-wt-ink tabular">{money(lead.quote_total)}</span>;
  return <span className="text-wt-muted">{lead.status === "walkthru_completed" ? "Pending" : "None"}</span>;
};

const Activity = ({ lead, now }) =>
  lead.live ? (
    <span className="font-semibold text-wt-accent">On call now</span>
  ) : (
    <span className="text-wt-muted">{ACTIVITY[lead.status]} {ago(lead.last_activity_at, now)}</span>
  );

export const LeadRow = ({ lead, selected, flash, now, onSelect, onAction }) => {
  const label = lead.status === "walkthru_initiated" && !lead.live ? "Open" : ACTIONS[lead.status] || "Open";
  const primary = lead.status === "new";
  return (
    <tr
      data-testid={`lead-row-${lead.id}`}
      onClick={() => onSelect(lead.id)}
      className={`cursor-pointer whitespace-nowrap border-t border-wt-line transition-colors duration-150 ${
        selected ? "bg-[#FFF6EF]" : "hover:bg-[#FAFBFC]"
      } ${flash ? "row-flash" : ""}`}
    >
      <td className="px-4 py-3">
        <p className="text-[15px] font-semibold text-wt-ink">{lead.name}</p>
        <p className="text-[13px] text-wt-muted tabular">{lead.phone}</p>
      </td>
      <td className="px-4 py-3">
        <span className="rounded-md bg-[#EEF0F3] px-2 py-1 text-[13px] font-semibold text-wt-ink">{SOURCES[lead.source]}</span>
      </td>
      <td className="px-4 py-3 text-[15px] text-wt-ink">{lead.ask}</td>
      <td className="px-4 py-3">
        <div className="flex flex-col items-start gap-1">
          <StatusPill key={lead.status} status={lead.status} flash={flash} testId={`lead-status-${lead.id}`} />
          {lead.escalated && <span className="text-[11px] font-bold uppercase tracking-wide text-[#B91C1C]">Escalated</span>}
        </div>
      </td>
      <td className="px-4 py-3 text-[15px]"><QuoteCell lead={lead} now={now} /></td>
      <td className="px-4 py-3 text-[14px]"><Activity lead={lead} now={now} /></td>
      <td className="px-4 py-3">
        <button
          data-testid={`lead-action-${lead.id}`}
          onClick={(e) => { e.stopPropagation(); onAction(lead, label); }}
          className={`min-h-[40px] whitespace-nowrap rounded-lg px-3.5 text-sm font-bold transition-colors duration-150 ${
            primary ? "bg-wt-accent text-white hover:bg-wt-accentDark" : "border border-wt-line bg-white text-wt-ink hover:border-wt-ink/30"
          }`}
        >
          {label}
        </button>
      </td>
    </tr>
  );
};
