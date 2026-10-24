import { House } from "lucide-react";
import { toast } from "sonner";

const NAV = ["Leads", "Sessions", "Quotes", "Payments", "Rate card and settings"];

export const Logo = ({ dark = true }) => (
  <div className="flex items-center gap-2.5">
    <span className="grid h-8 w-8 place-items-center rounded-lg bg-wt-accent text-white">
      <House className="h-4 w-4" strokeWidth={2.4} />
    </span>
    <span className={`font-display text-xl font-bold tracking-tight ${dark ? "text-white" : "text-wt-ink"}`}>Walkthru</span>
  </div>
);

const NavItem = ({ label, active }) => (
  <button
    data-testid={`sidebar-nav-${label.split(" ")[0].toLowerCase()}`}
    onClick={() => !active && toast(`${label} is coming next`, { description: "This demo focuses on the Leads view." })}
    className={`min-h-[44px] shrink-0 rounded-lg px-3 text-left text-[15px] transition-colors duration-150 ${
      active ? "bg-white/10 font-semibold text-white" : "text-white/75 hover:bg-white/5 hover:text-white"
    }`}
  >
    {label}
  </button>
);

export const Sidebar = ({ contractor }) => (
  <aside className="bg-wt-ink lg:sticky lg:top-0 lg:flex lg:h-screen lg:w-[232px] lg:shrink-0 lg:flex-col">
    <div className="flex items-center justify-between px-5 py-4 lg:px-6 lg:py-6">
      <Logo />
    </div>
    <nav className="flex gap-1 overflow-x-auto px-3 pb-3 lg:flex-1 lg:flex-col lg:overflow-visible lg:px-4">
      {NAV.map((label) => <NavItem key={label} label={label} active={label === "Leads"} />)}
    </nav>
    <div data-testid="sidebar-contractor-card" className="m-4 hidden rounded-xl bg-white/5 p-4 lg:block">
      <p className="text-sm font-bold text-white">{contractor?.name || "Apex Remodeling"}</p>
      <p className="mt-1 text-[13px] leading-snug text-white/70">
        Quotes go straight to homeowners. You can recall any quote.
      </p>
    </div>
  </aside>
);
