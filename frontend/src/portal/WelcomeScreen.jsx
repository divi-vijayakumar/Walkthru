import { Mic, ShieldCheck } from "lucide-react";
import { PortalHeader, PortalShell, PrimaryButton } from "@/portal/PortalShell";

const STEPS = ["Talk through your project", "Show us the space on camera, only if you want to", "Review your estimate, sign, and pay a small deposit"];

export const WelcomeScreen = ({ data, onTalk, onChat }) => (
  <PortalShell testId="welcome-screen">
    <PortalHeader contractor={data.contractor.name} logo />
    <h1 data-testid="welcome-title" className="mt-8 font-display text-[34px] font-bold leading-[1.1] tracking-tight text-wt-ink">
      Hi {data.lead.first_name}, let's walk through your {data.lead.ask.toLowerCase()}.
    </h1>
    <p className="mt-3 text-[17px] leading-relaxed text-wt-muted">
      Talk with our AI estimator. In a few minutes you'll have a priced quote, and you can change it just by asking.
    </p>
    <ol className="mt-6 rounded-2xl border border-wt-line bg-white px-4">
      {STEPS.map((s, i) => (
        <li key={s} className="flex items-center gap-3 border-b border-wt-line py-3.5 last:border-0">
          <span className="grid h-7 w-7 shrink-0 place-items-center rounded-full bg-wt-soft text-sm font-bold text-wt-accentDark">{i + 1}</span>
          <span className="text-[16px] font-medium text-wt-ink">{s}</span>
        </li>
      ))}
    </ol>
    <div className="mt-auto pt-10">
      <p data-testid="recording-notice" className="flex gap-2 text-[14px] leading-snug text-wt-muted">
        <ShieldCheck className="mt-0.5 h-4 w-4 shrink-0 text-wt-teal" />
        This call is recorded so we can build your quote. Your camera stays off until you turn it on.
      </p>
      <PrimaryButton data-testid="start-talking-btn" onClick={onTalk} className="mt-4">
        <Mic className="h-5 w-5" /> Start talking
      </PrimaryButton>
      <button data-testid="use-chat-btn" onClick={onChat}
        className="mt-3 min-h-[52px] w-full rounded-2xl border border-wt-line bg-white text-[16px] font-semibold text-wt-ink hover:border-wt-ink/30">
        Prefer to type? Use chat instead
      </button>
      <p className="mt-4 text-center text-[13px] text-wt-muted">
        Quotes are estimates until {data.contractor.name} confirms them on site.
      </p>
    </div>
  </PortalShell>
);
