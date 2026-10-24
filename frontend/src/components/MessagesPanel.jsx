import { useState } from "react";
import { MessageSquare, Send, Loader2 } from "lucide-react";
import { toast } from "sonner";
import { api, timeAgo } from "@/lib/api";
import { Panel } from "@/components/Panel";
import { LEAD } from "@/constants/testIds";

const Bubble = ({ m }) => {
  const mine = m.role === "contractor";
  return (
    <div data-testid={LEAD.message(m.id)} className={`flex ${mine ? "justify-end" : "justify-start"}`}>
      <div className={`max-w-[80%] rounded-lg px-3.5 py-2.5 text-sm leading-relaxed ${mine ? "bg-orange-500 text-zinc-950" : "bg-zinc-800 text-zinc-200"}`}>
        <p>{m.content}</p>
        <p className={`mt-1 font-mono text-[10px] ${mine ? "text-zinc-900/70" : "text-zinc-500"}`}>
          {mine ? "You" : "Customer"} · {timeAgo(m.created_at)}
        </p>
      </div>
    </div>
  );
};

export const MessagesPanel = ({ leadId, messages, onSent }) => {
  const [text, setText] = useState("");
  const [sending, setSending] = useState(false);

  const send = async (e) => {
    e.preventDefault();
    if (!text.trim()) return;
    setSending(true);
    try {
      const { data } = await api.post(`/leads/${leadId}/messages`, { role: "contractor", content: text });
      onSent(data);
      setText("");
    } catch {
      toast.error("Message failed to send");
    } finally {
      setSending(false);
    }
  };

  return (
    <Panel title="Messages" icon={MessageSquare} testId={LEAD.messagesPanel}>
      <div className="max-h-80 space-y-3 overflow-y-auto pr-1">
        {messages.length === 0 && <p className="py-6 text-center text-xs text-zinc-500">No messages yet.</p>}
        {messages.map((m) => <Bubble key={m.id} m={m} />)}
      </div>
      <form onSubmit={send} className="mt-4 flex gap-2">
        <input
          data-testid={LEAD.messageInput}
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder="Write a message to the customer…"
          className="h-10 flex-1 rounded-md border border-zinc-700 bg-zinc-900 px-3 text-sm text-zinc-100 placeholder:text-zinc-500 focus:border-orange-500 focus:outline-none"
        />
        <button
          data-testid={LEAD.sendMessage}
          type="submit"
          disabled={sending || !text.trim()}
          className="inline-flex h-10 items-center gap-2 rounded-md bg-orange-500 px-4 text-sm font-semibold text-zinc-950 transition-colors duration-150 hover:bg-orange-600 disabled:opacity-40"
        >
          {sending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
          Send
        </button>
      </form>
    </Panel>
  );
};
