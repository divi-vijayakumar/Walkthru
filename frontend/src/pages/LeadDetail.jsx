import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { ArrowLeft, Phone, Video, StickyNote, ScanSearch, Receipt } from "lucide-react";
import { toast } from "sonner";
import { api, timeAgo, STATUSES } from "@/lib/api";
import { Panel, EmptyState } from "@/components/Panel";
import { StatusSelect } from "@/components/StatusSelect";
import { StatusBadge } from "@/components/StatusBadge";
import { MessagesPanel } from "@/components/MessagesPanel";
import { Skeleton } from "@/components/ui/skeleton";
import { LEAD } from "@/constants/testIds";

const LeadHeader = ({ lead, onStatus }) => (
  <div className="flex flex-col gap-5 sm:flex-row sm:items-end sm:justify-between">
    <div>
      <div className="flex flex-wrap items-center gap-3">
        <p data-testid={LEAD.projectType} className="font-mono text-xs uppercase tracking-[0.2em] text-orange-500">{lead.project_type}</p>
        <StatusBadge status={lead.status} testId="lead-detail-status-badge" />
      </div>
      <h1 data-testid={LEAD.name} className="mt-2 text-4xl font-extrabold tracking-tight text-zinc-50 sm:text-5xl">{lead.customer_name}</h1>
      <div className="mt-3 flex flex-wrap items-center gap-4 text-sm text-zinc-400">
        <a data-testid={LEAD.phone} href={`tel:${lead.phone}`} className="inline-flex items-center gap-1.5 hover:text-orange-400">
          <Phone className="h-3.5 w-3.5" /> {lead.phone}
        </a>
        <span className="font-mono text-xs text-zinc-500">Received {timeAgo(lead.created_at)}</span>
      </div>
    </div>
    <div className="flex flex-col gap-1.5">
      <span className="font-mono text-[10px] uppercase tracking-[0.18em] text-zinc-500">Status</span>
      <StatusSelect value={lead.status} onChange={onStatus} />
    </div>
  </div>
);

const ScopePanel = () => (
  <Panel title="Extracted Scope" icon={ScanSearch} testId={LEAD.scopePanel}>
    <EmptyState icon={ScanSearch} title="No scope extracted yet" body="Rooms, measurements and line items pulled from the walkthrough video will appear here." />
  </Panel>
);

const QuotePanel = () => (
  <Panel title="Quote" icon={Receipt} testId={LEAD.quotePanel}>
    <EmptyState icon={Receipt} title="No quote generated yet" body="Once the scope is ready, a priced quote with a low–high range will show up here." />
  </Panel>
);

export default function LeadDetail() {
  const { leadId } = useParams();
  const [data, setData] = useState(null);
  const [notFound, setNotFound] = useState(false);

  useEffect(() => {
    setData(null);
    api.get(`/leads/${leadId}`)
      .then((r) => { setData(r.data); document.title = `${r.data.lead.customer_name} · Walkthru`; })
      .catch(() => setNotFound(true));
  }, [leadId]);

  const changeStatus = async (status) => {
    const prev = data.lead.status;
    setData((d) => ({ ...d, lead: { ...d.lead, status } }));
    try {
      await api.patch(`/leads/${leadId}/status`, { status });
      toast.success(`Status set to ${STATUSES[status].label}`);
    } catch {
      setData((d) => ({ ...d, lead: { ...d.lead, status: prev } }));
      toast.error("Couldn't update status");
    }
  };

  const addMessage = (m) => setData((d) => ({ ...d, messages: [...d.messages, m] }));

  return (
    <div data-testid={LEAD.page} className="mx-auto max-w-6xl px-5 py-8 sm:px-8 lg:px-12 lg:py-12">
      <Link data-testid={LEAD.back} to="/" className="inline-flex items-center gap-2 text-sm text-zinc-400 transition-colors hover:text-orange-400">
        <ArrowLeft className="h-4 w-4" /> All leads
      </Link>

      {notFound && <p data-testid={LEAD.notFound} className="mt-10 text-zinc-400">This lead doesn't exist.</p>}
      {!data && !notFound && <Skeleton className="mt-8 h-40 w-full bg-zinc-800/60" />}

      {data && (
        <div className="wt-rise mt-6">
          <LeadHeader lead={data.lead} onStatus={changeStatus} />
          <div className="mt-10 grid gap-6 lg:grid-cols-12">
            <div className="space-y-6 lg:col-span-7">
              <Panel title="Walkthrough video" icon={Video}>
                <video
                  data-testid={LEAD.video}
                  key={data.lead.video_url}
                  src={data.lead.video_url}
                  controls
                  playsInline
                  className="aspect-video w-full rounded-lg bg-black"
                />
              </Panel>
              <Panel title="Notes" icon={StickyNote}>
                <p data-testid={LEAD.notes} className="whitespace-pre-line text-sm leading-relaxed text-zinc-300">
                  {data.lead.notes || "No notes."}
                </p>
              </Panel>
              <MessagesPanel leadId={leadId} messages={data.messages} onSent={addMessage} />
            </div>
            <div className="space-y-6 lg:col-span-5">
              <ScopePanel />
              <QuotePanel />
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
