import Vapi from "@vapi-ai/web";
import { api } from "@/shared/api";
import { rangeOf } from "@/portal/voice/scripts";

export const TAKEOVER_LINE = "Let me connect you with our contractor. You'll get a call back right away.";

const listeners = () => {
  const set = new Set();
  return { add: (cb) => { set.add(cb); return () => set.delete(cb); }, emit: (...a) => set.forEach((cb) => cb(...a)) };
};

// Real voice call through the Vapi web SDK. Tool calls and end-of-call reports reach /api/vapi/* from Vapi.
export function createVapiAdapter({ token, data, mode = "first" }) {
  const captions = listeners();
  const ends = listeners();
  const vapi = new Vapi(data.voice.public_key);
  let ended = false;
  let tookOver = false;

  const finish = async () => {
    if (ended) return;
    ended = true;
    await api.post(`/portal/${token}/call/end`, {}).catch(() => {});
    ends.emit();
  };

  vapi.on("call-start", () => { api.post(`/portal/${token}/call/start`).catch(() => {}); });
  vapi.on("call-end", finish);
  vapi.on("error", () => finish());
  vapi.on("message", (m) => {
    if (m?.type !== "transcript" || !m.transcript) return;
    captions.emit({ role: m.role === "assistant" ? "assistant" : "user", text: m.transcript, final: m.transcriptType === "final" });
  });

  return {
    async start() {
      await vapi.start(data.voice.assistant_id, {
        variableValues: {
          customer_name: data.lead.name,
          contractor_name: data.contractor.name,
          ask: data.lead.ask,
          lead_token: token,
          current_quote: mode === "change" && data.quote ? `Version ${data.quote.version}, ${rangeOf(data.quote)}` : "",
        },
      });
      return { mic: true };
    },
    stop() {
      vapi.stop();
      setTimeout(finish, 1500);
    },
    setMuted(m) { vapi.setMuted(m); },
    injectInsight(text) {
      if (ended) return;
      vapi.send({ type: "add-message", message: { role: "system",
        content: `Camera update: ${text.replace(/\.$/, "")}. Mention it naturally at the next pause; don't interrupt the homeowner.` } });
    },
    takeOver() {
      if (ended || tookOver) return;
      tookOver = true;
      vapi.say(TAKEOVER_LINE, true);
    },
    onCaption: captions.add,
    onEnd: ends.add,
    onPrompt: () => () => {},
  };
}
