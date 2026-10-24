import { useEffect, useState } from "react";
import { Outlet } from "react-router-dom";
import { Menu, X } from "lucide-react";
import { api } from "@/lib/api";
import { Sidebar, Wordmark } from "@/components/Sidebar";
import { NAV } from "@/constants/testIds";

export const AppLayout = () => {
  const [contractor, setContractor] = useState(null);
  const [open, setOpen] = useState(false);

  useEffect(() => {
    api.get("/contractor").then((r) => setContractor(r.data)).catch(() => {});
  }, []);

  return (
    <div className="flex min-h-screen bg-[#09090b] text-zinc-100">
      <div className="sticky top-0 hidden h-screen lg:block">
        <Sidebar contractor={contractor} />
      </div>
      {open && (
        <div className="fixed inset-0 z-40 flex lg:hidden">
          <Sidebar contractor={contractor} onNavigate={() => setOpen(false)} />
          <button aria-label="Close menu" className="flex-1 bg-black/70" onClick={() => setOpen(false)} />
        </div>
      )}
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-30 flex h-14 items-center justify-between border-b border-zinc-800 bg-[#0c0c0f] px-5 lg:hidden">
          <Wordmark />
          <button data-testid={NAV.mobileMenu} onClick={() => setOpen(!open)} className="rounded-md p-2 text-zinc-300 hover:bg-zinc-800">
            {open ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
          </button>
        </header>
        <main className="wt-grid-bg flex-1">
          <Outlet context={{ contractor }} />
        </main>
      </div>
    </div>
  );
};
