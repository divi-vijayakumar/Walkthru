import { useState } from "react";
import { Loader2 } from "lucide-react";
import { toast } from "sonner";
import { Dialog, DialogContent, DialogDescription, DialogTitle } from "@/components/ui/dialog";
import { api, errorText } from "@/shared/api";
import { money } from "@/shared/format";

const METHODS = [["cash", "Cash"], ["check", "Check"], ["other", "Other"]];

export const RecordPaymentDialog = ({ payment, onClose, onDone }) => {
  const [method, setMethod] = useState("check");
  const [reference, setReference] = useState("");
  const [busy, setBusy] = useState(false);
  const save = async () => {
    setBusy(true);
    try {
      await api.post(`/payments/${payment.id}/record`, { method, reference });
      toast.success(`Deposit recorded for ${payment.lead_name}`);
      onDone();
    } catch (e) {
      toast.error(errorText(e));
    } finally {
      setBusy(false);
    }
  };
  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent data-testid="record-payment-dialog" className="max-w-md bg-white">
        <DialogTitle>Record a deposit</DialogTitle>
        <DialogDescription>{payment.lead_name} paid {money(payment.amount)} outside the portal. This marks the deposit as received.</DialogDescription>
        <div className="flex gap-2">
          {METHODS.map(([k, label]) => (
            <button key={k} data-testid={`record-method-${k}`} onClick={() => setMethod(k)}
              className={`min-h-[44px] flex-1 rounded-lg text-[14px] font-bold transition-colors duration-150 ${method === k ? "bg-wt-ink text-white" : "border border-wt-line"}`}>{label}</button>
          ))}
        </div>
        <label className="block text-[13px] font-semibold text-wt-muted">
          {method === "check" ? "Check number (optional)" : "Note (optional)"}
          <input data-testid="record-reference-input" value={reference} maxLength={80} onChange={(e) => setReference(e.target.value)}
            className="mt-1 h-11 w-full rounded-lg border border-wt-line px-3 text-[15px] text-wt-ink focus:border-wt-accent focus:outline-none" />
        </label>
        <button data-testid="record-payment-confirm-btn" onClick={save} disabled={busy}
          className="flex min-h-[48px] items-center justify-center gap-2 rounded-xl bg-wt-accent text-[15px] font-bold text-white disabled:opacity-60">
          {busy && <Loader2 className="h-4 w-4 animate-spin" />} Mark {money(payment.amount)} as paid
        </button>
      </DialogContent>
    </Dialog>
  );
};
