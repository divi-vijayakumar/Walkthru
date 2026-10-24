import { api } from "@/shared/api";
import { buildScript, failureLines } from "@/portal/voice/scripts";

const speakMs = (text) => 1400 + text.length * 48;

const listeners = () => {
  const set = new Set();
  return { add: (cb) => { set.add(cb); return () => set.delete(cb); }, emit: (...a) => set.forEach((cb) => cb(...a)) };
};

// Scripted conversation that drives the same backend tool and end-of-call logic, scoped to this portal link.
export function createMockAdapter({ token, data, mode = "first", chat = false }) {
  const captions = listeners();
  const ends = listeners();
  const prompts = listeners();
  const callId = `mock-${Date.now()}`;
  const c = {
    first: data.lead.first_name, contractor: data.contractor.name, agent: data.contractor.agent_name,
    ask: data.lead.ask.toLowerCase(),
  };
  const ctx = { user: [], lastUser: "", last: null, quote: data.quote };
  const transcript = [];
  const variableValues = { customer_name: data.lead.name, contractor_name: c.contractor, ask: data.lead.ask, lead_token: token };
  let stopped = false;
  let ended = false;
  let stream = null;
  let timer = null;
  let replyResolve = null;

  const sleep = (ms) => new Promise((r) => { timer = setTimeout(r, ms); });
  const emit = (role, text) => {
    transcript.push({ role, message: text });
    captions.emit({ role, text, final: true });
  };

  const callTool = async (name, args) => {
    const body = { message: { type: "tool-calls", call: { id: callId, assistantOverrides: { variableValues } },
      toolCallList: [{ id: `tc-${Date.now()}`, type: "function", function: { name, arguments: args } }] } };
    try {
      const { data: res } = await api.post(`/portal/${token}/agent/tools`, body, { timeout: 40000 });
      const r = res.results?.[0] || {};
      return r.error ? { status: "error", say: r.error } : JSON.parse(r.result);
    } catch {
      return { status: "error", say: "timeout" };
    }
  };

  const say = async (text) => {
    if (stopped) return;
    emit("assistant", text);
    await sleep(chat ? 900 : speakMs(text));
  };

  const userTurn = async (scripted) => {
    let text = scripted;
    if (chat) {
      prompts.emit(scripted);
      text = await new Promise((r) => { replyResolve = r; });
      prompts.emit(null);
    }
    if (stopped) return;
    emit("user", text);
    ctx.user.push(text);
    ctx.lastUser = text;
    await sleep(chat ? 500 : speakMs(text));
  };

  const finish = async () => {
    if (ended) return;
    ended = true;
    stopped = true;
    clearTimeout(timer);
    replyResolve?.("");
    stream?.getTracks().forEach((t) => t.stop());
    await api.post(`/portal/${token}/agent/end`, { message: { type: "end-of-call-report", endedReason: "customer-ended-call",
      call: { id: callId, assistantOverrides: { variableValues } }, artifact: { messages: transcript } } }).catch(() => {});
    ends.emit();
  };

  const run = async () => {
    for (const step of buildScript(c, mode)) {
      if (stopped) return;
      if (step.tool) {
        const r = await callTool(step.tool, step.args(ctx));
        if (stopped) return;
        if (r.status !== "ok" && r.status !== "limit_reached") {
          if (r.status === "needs_human" && !ctx.quote) await callTool("queue_quote_followup", { reason: r.say, summary: ctx.user.join(" ") });
          for (const line of failureLines(c, r, !!ctx.quote)) await say(line);
          break;
        }
        ctx.last = r;
        ctx.quote = r;
      } else if (step.role === "user") {
        await userTurn(step.text);
      } else {
        await say(typeof step.text === "function" ? step.text(ctx) : step.text);
      }
    }
    if (!stopped) await finish();
  };

  return {
    async start() {
      let mic = true;
      if (!chat) {
        try {
          stream = await navigator.mediaDevices.getUserMedia({ audio: true, video: false });
        } catch {
          mic = false;
        }
      }
      await api.post(`/portal/${token}/call/start`);
      run();
      return { mic };
    },
    stop: finish,
    setMuted(m) { stream?.getAudioTracks().forEach((t) => { t.enabled = !m; }); },
    sendText(text) { if (replyResolve && text.trim()) { const r = replyResolve; replyResolve = null; r(text.trim()); } },
    onCaption: captions.add,
    onEnd: ends.add,
    onPrompt: prompts.add,
  };
}
