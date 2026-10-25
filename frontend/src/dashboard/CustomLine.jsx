import { Fragment, useState } from "react";
import { Loader2 } from "lucide-react";
import { toast } from "sonner";
import { api, errorText } from "@/shared/api";
import { MoneyInput, TextField, isAmount } from "@/dashboard/settings/fields";

const STOP = new Set(["want", "would", "like", "this", "that", "with", "from", "have", "make", "some", "little", "please", "really", "just",
  "remove", "replace", "change", "build", "install", "take", "need", "they", "there", "their", "then", "also", "into", "onto", "about", "better"]);
const guessWords = (said) => [...new Set(said.toLowerCase().replace(/[^a-z\s]/g, " ").split(/\s+/).filter((w) => w.length > 3 && !STOP.has(w)))].slice(0, 3).join(", ");
const TIERS = ["Refresh", "Standard", "Premium"];

const Details = ({ d }) => (
  <dl className="mt-1 grid grid-cols-[auto_1fr] gap-x-3 gap-y-0.5 text-[13px]">
    {[["They said", d.words], ["Coming out", d.out], ["Going in", d.in], ["Size", d.size], ["Finish", d.finish]].map(([k, v]) => (
      <Fragment key={k}><dt className="text-wt-muted">{k}</dt><dd className="text-wt-ink">{v || "not answered yet"}</dd></Fragment>
    ))}
  </dl>
);

export const CustomLine = ({ leadId, line, onPriced }) => {
  const d = line.details || {};
  const [open, setOpen] = useState(false);
  const [label, setLabel] = useState(d.words ? d.words[0].toUpperCase() + d.words.slice(1) : "");
  const [tiers, setTiers] = useState(["", "", ""]);
  const [match, setMatch] = useState(guessWords(d.words || ""));
  const [busy, setBusy] = useState(false);
  const id = line.key || line.item_id;
  const valid = label.trim().length > 1 && tiers.every(isAmount) && tiers.some((t) => Number(t) > 0) && match.trim();
  const save = async () => {
    setBusy(true);
    try {
      const r = await api.post(`/itemizer/${leadId}/items/${id}/price`, { label: label.trim(), tiers: tiers.map(Number), match });
      toast.success(r.data.total ? "Priced and added to the rate card" : "Added to the rate card");
      onPriced(r.data);
    } catch (e) {
      toast.error(errorText(e));
    } finally {
      setBusy(false);
    }
  };
  return (
    <li data-testid={`custom-line-${id}`} className="border-t border-wt-line py-2 text-[14px]">
      <div className="flex justify-between gap-3"><span className="font-semibold">{line.label}</span><span className="font-semibold text-wt-accent">To be priced</span></div>
      <Details d={d} />
      {d.frames?.length > 0 && (
        <div className="mt-2 flex gap-2">{d.frames.map((f) => <img key={f.frame_url} src={f.frame_url} alt={f.label || "camera frame"} className="h-16 w-24 rounded-md object-cover" />)}</div>
      )}
      {!open ? (
        <button data-testid={`price-custom-btn-${id}`} onClick={() => setOpen(true)}
          className="mt-2 min-h-[40px] rounded-lg border border-wt-line px-3 text-[13px] font-bold transition-colors duration-150 hover:border-wt-ink/30">Price this job</button>
      ) : (
        <div data-testid={`price-custom-form-${id}`} className="mt-2 space-y-2 rounded-xl bg-wt-ground p-3">
          <TextField label="Name on the quote" value={label} onChange={setLabel} testId={`price-custom-label-${id}`} maxLength={80} />
          <div className="grid grid-cols-3 gap-2">
            {TIERS.map((t, k) => <MoneyInput key={t} label={t} value={tiers[k]} testId={`price-custom-tier-${k}-${id}`} onChange={(v) => setTiers((x) => x.map((y, j) => (j === k ? v : y)))} />)}
          </div>
          <TextField label="Words that should match it next time (comma separated)" value={match} onChange={setMatch} testId={`price-custom-match-${id}`} />
          <button data-testid={`price-custom-save-${id}`} onClick={save} disabled={!valid || busy}
            className="inline-flex min-h-[44px] items-center gap-2 rounded-lg bg-wt-accent px-4 text-sm font-bold text-white disabled:opacity-50">
            {busy && <Loader2 className="h-4 w-4 animate-spin" />} Save price and add to rate card
          </button>
        </div>
      )}
    </li>
  );
};
