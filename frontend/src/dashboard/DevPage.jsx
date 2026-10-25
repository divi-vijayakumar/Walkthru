import { useCallback, useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { toast } from "sonner";
import { api, errorText } from "@/shared/api";
import { SOURCES } from "@/shared/status";
import { StatusPill } from "@/shared/StatusPill";
import { showSmsToast } from "@/shared/smsToast";

const input = "h-11 rounded-lg border border-wt-line bg-white px-3 text-sm focus:border-wt-accent focus:outline-none";
const btn = "min-h-[44px] rounded-lg px-3.5 text-sm font-bold transition-colors";

const CreateLeadForm = ({ onCreated }) => {
  const [form, setForm] = useState({ name: "Test Homeowner", phone: "", ask: "Bathroom remodel", source: "website" });
  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value });
  const submit = async (e) => {
    e.preventDefault();
    try {
      const { data } = await api.post("/leads", form);
      toast.success(`Lead created: ${data.lead.name}`);
      if (data.agent) showSmsToast(data.agent.sms, data.agent.link, data.lead.name);
      onCreated();
    } catch (err) {
      toast.error(errorText(err, "Check the name and phone number"));
    }
  };
  return (
    <form onSubmit={submit} className="grid gap-3 rounded-2xl border border-wt-line bg-white p-5 sm:grid-cols-2 lg:grid-cols-5">
      <input data-testid="dev-name" className={input} value={form.name} onChange={set("name")} placeholder="Name" />
      <input data-testid="dev-phone" className={input} value={form.phone} onChange={set("phone")} placeholder="Phone, e.g. (408) 555-0100" required />
      <select data-testid="dev-ask" className={input} value={form.ask} onChange={set("ask")}>
        {["Bathroom remodel", "Kitchen remodel", "Deck repair"].map((a) => <option key={a}>{a}</option>)}
      </select>
      <select data-testid="dev-source" className={input} value={form.source} onChange={set("source")}>
        {Object.entries(SOURCES).map(([v, l]) => <option key={v} value={v}>{l}</option>)}
      </select>
      <button data-testid="dev-create-lead" className={`${btn} bg-wt-accent text-white hover:bg-wt-accentDark`}>Create new lead</button>
    </form>
  );
};

const CHUNK = 4 * 1024 * 1024;

const VideoUpload = ({ lead }) => {
  const input = useRef(null);
  const [pct, setPct] = useState(null);
  const send = async (file) => {
    const id = `${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;
    const parts = Math.ceil(file.size / CHUNK);
    try {
      for (let i = 0; i < parts; i += 1) {
        await api.post(`/dev/uploads/${id}/chunk?index=${i}`, file.slice(i * CHUNK, (i + 1) * CHUNK),
          { headers: { "Content-Type": "application/octet-stream" }, timeout: 120000 });
        setPct(Math.round(((i + 1) / parts) * 100));
      }
      await api.post(`/dev/leads/${lead.id}/video`, { upload_id: id, content_type: file.type || "video/mp4" }, { timeout: 300000 });
      toast.success(`${lead.name}: video stored`, { description: "Any open camera questions for this lead are being checked now." });
    } catch (e) {
      toast.error(errorText(e, "Upload failed"));
    } finally {
      setPct(null);
      if (input.current) input.current.value = "";
    }
  };
  return (
    <>
      <input ref={input} type="file" accept="video/*" className="hidden" data-testid={`dev-video-input-${lead.id}`}
        onChange={(e) => e.target.files[0] && send(e.target.files[0])} />
      <button data-testid={`dev-video-${lead.id}`} disabled={pct !== null} onClick={() => input.current?.click()}
        className={`${btn} border border-wt-line bg-white disabled:opacity-60`}>
        {pct === null ? "Upload walkthrough video" : `Uploading ${pct}%`}
      </button>
    </>
  );
};

const DevLeadRow = ({ lead, onChange }) => {
  const run = async (path, label) => {
    try {
      const { data } = await api.post(`/dev/leads/${lead.id}/${path}`);
      toast.success(`${lead.name}: ${label}`);
      if (data.sms) showSmsToast(data.sms, data.link || lead.portal_link, lead.name);
      onChange();
    } catch (e) {
      toast.error(errorText(e));
    }
  };
  const done = ["deposit_received", "dropped"].includes(lead.status);
  return (
    <li data-testid={`dev-lead-${lead.id}`} className="flex flex-wrap items-center gap-3 border-t border-wt-line px-5 py-3">
      <div className="min-w-[160px] flex-1">
        <p className="font-semibold">{lead.name}</p>
        <p className="text-xs text-wt-muted">{lead.phone} · {lead.ask}</p>
      </div>
      <StatusPill status={lead.status} />
      {lead.portal_token && (
        <Link data-testid={`dev-portal-${lead.id}`} to={`/w/${lead.portal_token}`} target="_blank"
          className={`${btn} inline-flex items-center border border-wt-line bg-white`}>Open portal</Link>
      )}
      {!done && <VideoUpload lead={lead} />}
      <button data-testid={`dev-advance-${lead.id}`} disabled={done} onClick={() => run("advance", "advanced")}
        className={`${btn} bg-wt-ink text-white disabled:opacity-40`}>Advance one status</button>
      <button data-testid={`dev-drop-${lead.id}`} disabled={done} onClick={() => run("drop", "dropped")}
        className={`${btn} border border-wt-line bg-white text-[#B91C1C] disabled:opacity-40`}>Drop</button>
    </li>
  );
};

export default function DevPage() {
  const [leads, setLeads] = useState([]);
  const [config, setConfig] = useState(null);
  const load = useCallback(() => api.get("/dashboard").then((r) => setLeads(r.data.leads)), []);

  useEffect(() => {
    document.title = "Demo helper · Walkthru";
    load();
    api.get("/dev/config").then((r) => setConfig(r.data));
  }, [load]);

  const reset = async () => {
    await api.post("/dev/reset");
    toast.success("Sample data reset");
    load();
  };

  return (
    <div data-testid="dev-page" className="mx-auto min-h-screen max-w-5xl px-4 py-8">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="font-display text-3xl font-bold">Demo helper</h1>
          <p className="text-sm text-wt-muted">Rehearse without a live call. Open the dashboard in another tab to watch it update.</p>
        </div>
        <div className="flex gap-2">
          <Link to="/" className={`${btn} inline-flex items-center border border-wt-line bg-white`}>Dashboard</Link>
          <button data-testid="dev-reset" onClick={reset} className={`${btn} border border-wt-line bg-white`}>Reset sample data</button>
        </div>
      </div>
      {config && (
        <p data-testid="dev-config" className="mt-4 rounded-lg bg-white px-4 py-3 text-sm text-wt-muted">
          Voice: <b>{config.voice_mode}</b> · Messages ({config.channel === "whatsapp" ? "WhatsApp" : "SMS"}): <b>{config.twilio_configured ? `Twilio on, ${config.allowlist_count} allow-listed` : "simulated"}</b> · Tool simulate mode: <b>{config.simulate_mode}</b>
        </p>
      )}
      <h2 className="mb-2 mt-6 text-sm font-bold uppercase tracking-wide text-wt-muted">New lead</h2>
      <CreateLeadForm onCreated={load} />
      <h2 className="mb-2 mt-8 text-sm font-bold uppercase tracking-wide text-wt-muted">Leads</h2>
      <ul className="overflow-hidden rounded-2xl border border-wt-line bg-white">
        {leads.map((l) => <DevLeadRow key={l.id} lead={l} onChange={load} />)}
      </ul>
    </div>
  );
}
