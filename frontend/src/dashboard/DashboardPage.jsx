import { useCallback, useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { api, errorText } from "@/shared/api";
import { STATUS } from "@/shared/status";
import { useNow } from "@/shared/useNow";
import { showSmsToast } from "@/shared/smsToast";
import { Sidebar } from "@/dashboard/Sidebar";
import { DashboardHeader } from "@/dashboard/DashboardHeader";
import { WeekLine, VisitSection } from "@/dashboard/WeekLine";
import { LeadTable } from "@/dashboard/LeadTable";
import { LeadDrawer } from "@/dashboard/LeadDrawer";

const useDashboard = () => {
  const [data, setData] = useState(null);
  const [flash, setFlash] = useState({});
  const prev = useRef(null);

  const load = useCallback(async () => {
    const { data: d } = await api.get("/dashboard");
    if (prev.current) {
      const changed = {};
      d.leads.forEach((l) => {
        const before = prev.current[l.id];
        if (!before) toast(`New lead: ${l.name}`, { description: l.ask });
        else if (before !== l.status) {
          changed[l.id] = true;
          toast(`${l.name}: ${STATUS[l.status].label}`);
        }
      });
      if (Object.keys(changed).length) {
        setFlash((f) => ({ ...f, ...changed }));
        setTimeout(() => setFlash((f) => Object.fromEntries(Object.entries(f).filter(([k]) => !changed[k]))), 2500);
      }
    }
    prev.current = Object.fromEntries(d.leads.map((l) => [l.id, l.status]));
    setData(d);
  }, []);

  useEffect(() => {
    load().catch(() => toast.error("Couldn't load leads"));
    const id = setInterval(() => load().catch(() => {}), 3000);
    return () => clearInterval(id);
  }, [load]);

  return { data, flash, load };
};

export default function DashboardPage() {
  const { data, flash, load } = useDashboard();
  const [selectedId, setSelectedId] = useState(null);
  const [weekPick, setWeekPick] = useState(null);
  const [simulating, setSimulating] = useState(false);
  const drawerRef = useRef(null);
  const now = useNow(1000);

  useEffect(() => { document.title = "Leads · Walkthru"; }, []);

  const select = (id) => {
    setSelectedId(id);
    if (window.innerWidth < 1280) drawerRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  const onAction = async (lead, label) => {
    if (label !== "Start agent" && label !== "Resend") return select(lead.id);
    try {
      const { data: r } = await api.post(`/leads/${lead.id}/start-agent`);
      showSmsToast(r.sms, r.link, lead.name);
      load();
    } catch (e) {
      toast.error(errorText(e));
    }
  };

  const toggleAgent = async (on) => {
    await api.patch("/contractor", { agent_enabled: on });
    toast(on ? "Agent on: new leads get texted automatically" : "Agent off: start each lead yourself");
    load();
  };

  const simulate = async () => {
    setSimulating(true);
    try {
      const { data: r } = await api.post("/dev/simulate-dhivya", null, { timeout: 60000 });
      if (r.agent) showSmsToast(r.agent.sms, r.agent.link, r.lead.name);
      else toast(`${r.lead.name} re-added`, { description: "Agent is off, so press Start agent to send her invite" });
      setSelectedId(r.lead.id);
      load();
    } catch (e) {
      toast.error(errorText(e, "Couldn't restart Dhivya"));
    } finally {
      setSimulating(false);
    }
  };

  const selected = data?.leads.find((l) => l.id === selectedId) || data?.leads[0];

  return (
    <div className="min-h-screen bg-wt-ground lg:flex">
      <Sidebar contractor={data?.contractor} />
      <main data-testid="dashboard-page" className="min-w-0 flex-1 px-4 py-6 sm:px-6 lg:px-8 lg:py-8">
        <DashboardHeader contractor={data?.contractor} onToggle={toggleAgent} simulating={simulating} onSimulate={simulate} />
        {!data && <div className="mt-6 h-64 animate-pulse rounded-2xl bg-white" />}
        {data && (
          <>
            <WeekLine week={data.week} active={weekPick} onPick={setWeekPick} />
            <VisitSection visits={data.visits} onDone={load} />
            <div className="mt-4 grid gap-4 xl:grid-cols-[minmax(0,1fr)_340px]">
              <LeadTable leads={weekPick ? data.leads.filter((l) => data.week[weekPick].includes(l.id)) : data.leads}
                selectedId={selected?.id} flash={flash} now={now} onSelect={select} onAction={onAction} />
              <div ref={drawerRef}>{selected && <LeadDrawer lead={selected} now={now} onChanged={load} />}</div>
            </div>
          </>
        )}
      </main>
    </div>
  );
}
