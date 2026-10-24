import { Check } from "lucide-react";
import { FLOW, JOURNEY } from "@/shared/status";
import { timeOfDay } from "@/shared/format";

const lastAt = (history, status) => [...history].reverse().find((h) => h.status === status)?.at;

const Dot = ({ state }) => {
  if (state === "done") {
    return (
      <span className="grid h-5 w-5 place-items-center rounded-full bg-wt-teal text-white">
        <Check className="h-3 w-3" strokeWidth={3.5} />
      </span>
    );
  }
  if (state === "current") return <span className="h-5 w-5 rounded-full border-[3px] border-[#FBD5BC] bg-wt-accent" />;
  return <span className="h-5 w-5 rounded-full border-2 border-[#C9CFD8] bg-white" />;
};

export const Journey = ({ lead }) => {
  const idx = FLOW.indexOf(lead.status);
  return (
    <div data-testid="lead-journey" className="mt-5">
      <p className="text-sm font-bold text-wt-ink">Journey</p>
      {lead.status === "dropped" && <p className="mt-1 text-[13px] font-semibold text-[#B91C1C]">This lead dropped off.</p>}
      <ol className="mt-2 space-y-2">
        {FLOW.map((s, i) => {
          const at = lastAt(lead.status_history, s);
          const state = i === idx ? (s === "deposit_received" ? "done" : "current") : at && (idx === -1 || i < idx) ? "done" : "todo";
          return (
            <li key={s} data-testid={`journey-${s}`} className="flex items-center gap-2.5">
              <Dot state={state} />
              <span className={`flex-1 text-[14px] ${state === "current" ? "font-bold text-wt-ink" : state === "done" ? "text-wt-ink" : "text-wt-muted"}`}>
                {JOURNEY[s]}
              </span>
              {at && state !== "todo" && (
                <span className={`text-[13px] tabular ${state === "current" ? "font-bold text-wt-ink" : "text-wt-muted"}`}>{timeOfDay(at)}</span>
              )}
            </li>
          );
        })}
      </ol>
    </div>
  );
};
