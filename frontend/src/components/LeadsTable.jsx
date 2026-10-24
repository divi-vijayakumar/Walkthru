import { useNavigate } from "react-router-dom";
import { ChevronRight, Video } from "lucide-react";
import { StatusBadge } from "@/components/StatusBadge";
import { timeAgo } from "@/lib/api";
import { DASHBOARD } from "@/constants/testIds";

const LeadRow = ({ lead, index }) => {
  const navigate = useNavigate();
  return (
    <tr
      data-testid={DASHBOARD.row(lead.id)}
      onClick={() => navigate(`/leads/${lead.id}`)}
      style={{ animationDelay: `${index * 70}ms` }}
      className="wt-rise group cursor-pointer border-t border-zinc-800/80 transition-colors duration-150 hover:bg-zinc-800/40"
    >
      <td className="px-6 py-4">
        <div className="flex items-center gap-3">
          <span className="grid h-9 w-9 shrink-0 place-items-center rounded-md bg-zinc-800 text-zinc-400 transition-colors group-hover:bg-orange-500/15 group-hover:text-orange-400">
            <Video className="h-4 w-4" />
          </span>
          <div>
            <p className="text-sm font-semibold text-zinc-100">{lead.customer_name}</p>
            <p className="font-mono text-xs text-zinc-500 sm:hidden">{lead.project_type}</p>
          </div>
        </div>
      </td>
      <td className="hidden px-6 py-4 text-sm text-zinc-300 sm:table-cell">{lead.project_type}</td>
      <td className="hidden px-6 py-4 font-mono text-xs text-zinc-400 md:table-cell">{lead.phone}</td>
      <td className="px-6 py-4"><StatusBadge status={lead.status} testId={DASHBOARD.status(lead.id)} /></td>
      <td className="hidden px-6 py-4 font-mono text-xs text-zinc-500 md:table-cell">{timeAgo(lead.created_at)}</td>
      <td className="px-4 py-4 text-right">
        <ChevronRight className="ml-auto h-4 w-4 text-zinc-600 transition-transform duration-200 group-hover:translate-x-1 group-hover:text-orange-400" />
      </td>
    </tr>
  );
};

export const LeadsTable = ({ leads }) => (
  <div className="overflow-hidden rounded-xl border border-zinc-800 bg-[#18181b]">
    <table data-testid={DASHBOARD.table} className="w-full text-left">
      <thead>
        <tr className="font-mono text-[10px] uppercase tracking-[0.18em] text-zinc-500">
          <th className="px-6 py-3 font-medium">Customer</th>
          <th className="hidden px-6 py-3 font-medium sm:table-cell">Project</th>
          <th className="hidden px-6 py-3 font-medium md:table-cell">Phone</th>
          <th className="px-6 py-3 font-medium">Status</th>
          <th className="hidden px-6 py-3 font-medium md:table-cell">Received</th>
          <th className="w-10" />
        </tr>
      </thead>
      <tbody>
        {leads.map((lead, i) => <LeadRow key={lead.id} lead={lead} index={i} />)}
      </tbody>
    </table>
  </div>
);
