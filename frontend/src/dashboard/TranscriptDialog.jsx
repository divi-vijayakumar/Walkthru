import { useEffect, useState } from "react";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { api } from "@/shared/api";
import { timeOfDay } from "@/shared/format";

const ROLE = { assistant: "Agent", user: "Homeowner", system: "System" };

export const TranscriptDialog = ({ lead, open, onOpenChange }) => {
  const [sessions, setSessions] = useState(null);

  useEffect(() => {
    if (!open) { return; }
    setSessions(null);
    api.get(`/leads/${lead.id}/transcript`).then((r) => setSessions(r.data.sessions)).catch(() => setSessions([]));
  }, [open, lead.id]);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent data-testid="transcript-dialog" className="max-h-[80vh] overflow-y-auto bg-white sm:max-w-lg">
        <DialogHeader>
          <DialogTitle className="font-display text-xl">Transcript, {lead.name}</DialogTitle>
          <DialogDescription>Every walkthrough call with this homeowner, newest first.</DialogDescription>
        </DialogHeader>
        {!sessions && <p className="text-sm text-wt-muted">Loading...</p>}
        {sessions?.length === 0 && <p data-testid="transcript-empty" className="text-sm text-wt-muted">No calls yet.</p>}
        {sessions?.map((s) => (
          <div key={s.id} className="border-t border-wt-line pt-3">
            <p className="text-xs font-semibold uppercase tracking-wide text-wt-muted">
              Call at {timeOfDay(s.started_at)} {s.ended_at ? "" : "(live)"}
            </p>
            {(s.transcript || []).length === 0 && <p className="mt-2 text-sm text-wt-muted">Nothing said yet.</p>}
            {(s.transcript || []).map((t, i) => (
              <p key={i} className="mt-2 text-[14px] leading-relaxed">
                <span className="font-bold">{ROLE[t.role] || t.role}: </span>{t.text}
              </p>
            ))}
          </div>
        ))}
      </DialogContent>
    </Dialog>
  );
};
