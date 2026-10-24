import { NavLink } from "react-router-dom";
import { LayoutDashboard, HardHat } from "lucide-react";
import { NAV } from "@/constants/testIds";

export const Wordmark = ({ testId = NAV.wordmark }) => (
  <div data-testid={testId} className="flex items-center gap-2">
    <span className="grid h-7 w-7 place-items-center rounded-md bg-orange-500 font-mono text-sm font-bold text-zinc-950">
      W
    </span>
    <span className="font-display text-xl font-extrabold tracking-tight text-zinc-50">
      Walkthru<span className="text-orange-500">.</span>
    </span>
  </div>
);

export const Sidebar = ({ contractor, onNavigate }) => (
  <aside className="flex h-full w-64 flex-col border-r border-zinc-800 bg-[#0c0c0f]">
    <div className="px-6 pb-6 pt-7">
      <Wordmark />
      <p className="mt-3 text-xs leading-relaxed text-zinc-500">Walk through your project. Get your quote.</p>
    </div>
    <nav className="flex-1 px-3">
      <p className="px-3 pb-2 font-mono text-[10px] uppercase tracking-[0.2em] text-zinc-600">Workspace</p>
      <NavLink
        to="/"
        end={false}
        onClick={onNavigate}
        data-testid={NAV.leadsLink}
        className="group flex items-center gap-3 rounded-md border-l-2 border-orange-500 bg-zinc-900 px-3 py-2.5 text-sm font-medium text-zinc-50 transition-colors duration-200 hover:bg-zinc-800"
      >
        <LayoutDashboard className="h-4 w-4 text-orange-500" />
        Leads
      </NavLink>
    </nav>
    <div data-testid={NAV.contractorCard} className="m-3 rounded-lg border border-zinc-800 bg-zinc-900/60 p-4">
      <div className="flex items-center gap-3">
        <span className="grid h-9 w-9 place-items-center rounded-md bg-zinc-800 text-orange-400">
          <HardHat className="h-4 w-4" />
        </span>
        <div className="min-w-0">
          <p className="truncate text-sm font-semibold text-zinc-100">{contractor?.name || "Loading…"}</p>
          <p className="font-mono text-[11px] text-zinc-500">Demo contractor</p>
        </div>
      </div>
    </div>
  </aside>
);
