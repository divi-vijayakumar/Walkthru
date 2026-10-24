import { toast } from "sonner";
import { copyText } from "@/shared/format";

export const showSmsToast = (sms, link, name) => {
  if (!sms) return;
  const action = link
    ? { label: "Copy link", onClick: () => copyText(link).then((ok) => ok && toast.success("Link copied")) }
    : undefined;
  if (sms.sent) {
    toast.success(`SMS sent to ${name}`, { description: sms.to, action, duration: 8000 });
  } else if (sms.simulated) {
    toast("Sent (simulated)", {
      description: `${sms.reason}. Message to ${name}: "${sms.body}"`,
      action,
      duration: 12000,
    });
  } else {
    toast.error("SMS failed", { description: sms.error, action, duration: 12000 });
  }
};
