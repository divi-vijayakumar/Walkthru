import { useState } from "react";
import { Phone } from "lucide-react";
import { toast } from "sonner";
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription,
  AlertDialogFooter, AlertDialogHeader, AlertDialogTitle, AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
import { api, errorText } from "@/shared/api";
import { SOURCES } from "@/shared/status";
import { OnCallCard } from "@/dashboard/OnCallCard";
import { Journey } from "@/dashboard/Journey";
import { TranscriptDialog } from "@/dashboard/TranscriptDialog";
import { SeenFrame } from "@/shared/SeenFrame";
import { money, range } from "@/shared/format";

const QuoteLines = ({ quote }) => (
  <div data-testid="drawer-quote" className="mt-5 rounded-xl border border-wt-line p-3.5">
    <div className="flex items-baseline justify-between gap-2">
      <p className="text-sm font-bold text-wt-ink">Quote v{quote.version}</p>
      <p className="text-[13px] text-wt-muted tabular">{range(quote)}</p>
    </div>
    <ul className="mt-2">
      {(quote.line_items || []).map((i) => (
        <li key={i.key} data-testid={`drawer-line-${i.key}`} className="flex items-center justify-between gap-2 border-t border-wt-line py-2 text-[14px]">
          <span className="flex items-center gap-2">{i.label}<SeenFrame item={i} /></span>
          <span className="font-bold tabular">{i.amount < 0 ? `-${money(-i.amount)}` : money(i.amount)}</span>
        </li>
      ))}
    </ul>
  </div>
);

const TakeoverPrompt = ({ lead }) => (
  <div data-testid="takeover-prompt" className="mt-4 rounded-xl border border-[#F5C7A6] bg-wt-soft p-3.5">
    <p className="text-sm font-bold text-[#8A2F0B]">You're taking over</p>
    <p className="mt-0.5 text-[13px] text-[#8A2F0B]">Call {lead.name.split(" ")[0]} now. The agent will hand off.</p>
    <a data-testid="takeover-call-link" href={`tel:${lead.phone}`}
      className="mt-2.5 inline-flex min-h-[44px] items-center gap-2 rounded-lg bg-white px-3.5 text-sm font-bold text-wt-ink">
      <Phone className="h-4 w-4" /> {lead.phone}
    </a>
  </div>
);

const RecallButton = ({ lead, onDone }) => (
  <AlertDialog>
    <AlertDialogTrigger asChild>
      <button data-testid="recall-quote-btn" className="mt-3 min-h-[44px] w-full rounded-lg text-sm font-bold text-[#B91C1C] hover:bg-[#FDE2E2]">
        Recall quote
      </button>
    </AlertDialogTrigger>
    <AlertDialogContent className="bg-white">
      <AlertDialogHeader>
        <AlertDialogTitle>Recall {lead.name}'s quote?</AlertDialogTitle>
        <AlertDialogDescription>
          The homeowner will no longer see this price. Any unsigned contract is voided and the lead returns to
          "Walkthru completed" with a 15 minute quote timer.
        </AlertDialogDescription>
      </AlertDialogHeader>
      <AlertDialogFooter>
        <AlertDialogCancel data-testid="recall-cancel">Keep quote</AlertDialogCancel>
        <AlertDialogAction data-testid="recall-confirm" className="bg-[#B91C1C] hover:bg-[#991B1B]" onClick={onDone}>
          Recall quote
        </AlertDialogAction>
      </AlertDialogFooter>
    </AlertDialogContent>
  </AlertDialog>
);

export const LeadDrawer = ({ lead, now, onChanged }) => {
  const [showTranscript, setShowTranscript] = useState(false);
  const post = async (path, ok) => {
    try {
      await api.post(`/leads/${lead.id}/${path}`);
      toast.success(ok);
      onChanged();
    } catch (e) {
      toast.error(errorText(e));
    }
  };

  return (
    <aside data-testid="lead-drawer" className="h-fit rounded-2xl border border-wt-line bg-white p-5 xl:sticky xl:top-6">
      <h2 data-testid="drawer-name" className="font-display text-2xl font-bold text-wt-ink">{lead.name}</h2>
      <p className="text-sm text-wt-muted">{SOURCES[lead.source]} · {lead.ask}</p>
      {lead.status === "walkthru_initiated" && <OnCallCard lead={lead} now={now} />}
      <Journey lead={lead} />
      {lead.escalated && <TakeoverPrompt lead={lead} />}
      {lead.quote && <QuoteLines quote={lead.quote} />}
      <div className={`mt-5 grid gap-3 ${lead.status === "walkthru_initiated" ? "grid-cols-2" : "grid-cols-1"}`}>
        {lead.status === "walkthru_initiated" && <button data-testid="take-over-btn" onClick={() => post("take-over", "You're on it. Call the homeowner now.")}
          className="min-h-[44px] rounded-lg bg-wt-accent px-3 text-[15px] font-bold text-white transition-colors hover:bg-wt-accentDark">
          Take over call
        </button>}
        <button data-testid="transcript-btn" onClick={() => setShowTranscript(true)}
          className="min-h-[44px] rounded-lg border border-wt-line bg-white px-3 text-[15px] font-bold text-wt-ink hover:border-wt-ink/30">
          Transcript
        </button>
      </div>
      {lead.quote && lead.status !== "deposit_received" && (
        <RecallButton lead={lead} onDone={() => post("recall-quote", "Quote recalled")} />
      )}
      <p className="mt-4 text-[13px] leading-snug text-wt-muted">
        Quotes reach the homeowner without your approval. You can recall a quote at any time from its lead.
      </p>
      <TranscriptDialog lead={lead} open={showTranscript} onOpenChange={setShowTranscript} />
    </aside>
  );
};
