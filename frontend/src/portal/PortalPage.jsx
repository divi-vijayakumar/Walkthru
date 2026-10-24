import { useCallback, useEffect, useState } from "react";
import { useParams, useSearchParams } from "react-router-dom";
import { toast } from "sonner";
import { api, errorText } from "@/shared/api";
import { createVoiceAdapter } from "@/portal/voice/voiceAdapter";
import { WelcomeScreen } from "@/portal/WelcomeScreen";
import { CallScreen } from "@/portal/CallScreen";
import { ChatScreen } from "@/portal/ChatScreen";
import { QuoteScreen } from "@/portal/QuoteScreen";
import { ClosedScreen, ConfirmingScreen, ContractScreen, DepositScreen, DoneScreen, FallbackScreen } from "@/portal/StageScreens";
import { PortalShell } from "@/portal/PortalShell";

const screenFor = (d) => {
  const s = d.lead.status;
  if (["new", "invited", "walkthru_initiated"].includes(s)) return "welcome";
  if (s === "walkthru_completed") return "fallback";
  if (s === "quote_generated") return d.quote ? "quote" : "fallback";
  return { contract_sent: "contract", pending_deposit: "deposit", deposit_received: "done" }[s] || "closed";
};

export default function PortalPage() {
  const { token } = useParams();
  const [data, setData] = useState(null);
  const [missing, setMissing] = useState(false);
  const [call, setCall] = useState(null);
  const [signName, setSignName] = useState("");
  const [busy, setBusy] = useState(false);
  const [params, setParams] = useSearchParams();
  const sessionId = params.get("session_id");

  const load = useCallback(() => api.get(`/portal/${token}`).then((r) => { setData(r.data); return r.data; }), [token]);

  useEffect(() => {
    document.title = "Your quote · Walkthru";
    load().catch(() => setMissing(true));
  }, [load]);

  useEffect(() => {
    if (params.get("payment") === "cancelled") {
      toast("Payment cancelled", { description: "Your deposit is still due whenever you're ready." });
      setParams({}, { replace: true });
    }
  }, [params, setParams]);

  useEffect(() => {
    if (!sessionId) { return undefined; }
    let tries = 0;
    const id = setInterval(async () => {
      tries += 1;
      try {
        const { data: s } = await api.get(`/payments/status/${sessionId}`);
        if (s.payment_status === "paid" || s.status === "expired" || tries >= 20) {
          clearInterval(id);
          if (s.payment_status !== "paid") toast.error("We couldn't confirm the payment", { description: "If you were charged, Apex will follow up." });
          await load();
          setParams({}, { replace: true });
        }
      } catch {
        if (tries >= 20) { clearInterval(id); setParams({}, { replace: true }); }
      }
    }, 2000);
    return () => clearInterval(id);
  }, [sessionId, load, setParams]);

  const screen = call ? call.kind : data ? (sessionId && data.lead.status === "pending_deposit" ? "confirming" : screenFor(data)) : null;

  useEffect(() => {
    if (screen !== "fallback") { return undefined; }
    const id = setInterval(() => load().catch(() => {}), 5000);
    return () => clearInterval(id);
  }, [screen, load]);

  const startCall = (mode, chat = false) => {
    const adapter = createVoiceAdapter({ token, data, mode, chat });
    setCall({ adapter, kind: chat ? "chat" : "call" });
    adapter.start()
      .then((r) => { if (r?.mic === false) toast("Microphone not available", { description: "The demo call continues with a scripted conversation." }); })
      .catch((e) => { toast.error(errorText(e, "Couldn't start the call")); setCall(null); });
  };

  const onEnded = () => { load().finally(() => setCall(null)); };

  const act = async (fn) => {
    setBusy(true);
    try { await fn(); await load(); } catch (e) { toast.error(errorText(e)); } finally { setBusy(false); }
  };

  if (missing) return <PortalShell testId="portal-missing"><p className="mt-20 text-center text-wt-muted">This link is not valid.</p></PortalShell>;
  if (!data) return <PortalShell testId="portal-loading"><div className="mt-20 h-40 animate-pulse rounded-2xl bg-white" /></PortalShell>;

  const props = { data, token };
  switch (screen) {
    case "call": return <CallScreen {...props} adapter={call.adapter} onEnded={onEnded} />;
    case "chat": return <ChatScreen {...props} adapter={call.adapter} onEnded={onEnded} />;
    case "welcome": return <WelcomeScreen data={data} onTalk={() => startCall("first")} onChat={() => startCall("first", true)} />;
    case "quote":
      return <QuoteScreen data={data} busy={busy} onTalk={() => startCall("change")}
        onSign={(name) => act(async () => { setSignName(name); await api.post(`/portal/${token}/contract/open`); })} />;
    case "contract":
      return <ContractScreen data={data} busy={busy} initialName={signName}
        onSign={(name) => act(() => api.post(`/portal/${token}/contract/sign`, { name }))} />;
    case "deposit":
      return <DepositScreen data={data} busy={busy}
        onPay={async () => {
          setBusy(true);
          try {
            const { data: r } = await api.post(`/portal/${token}/deposit/checkout`, { origin_url: window.location.origin });
            window.location.href = r.checkout_url;
          } catch (e) {
            toast.error(errorText(e, "Couldn't open checkout"));
            setBusy(false);
          }
        }} />;
    case "confirming": return <ConfirmingScreen data={data} />;
    case "done": return <DoneScreen data={data} />;
    case "fallback": return <FallbackScreen data={data} />;
    default: return <ClosedScreen data={data} />;
  }
}
