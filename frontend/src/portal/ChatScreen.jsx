import { useEffect, useRef, useState } from "react";
import { Send } from "lucide-react";
import { EstimateCard } from "@/portal/EstimateCard";
import { PortalHeader } from "@/portal/PortalShell";
import { useCallFeed, useLiveQuote } from "@/portal/useCall";

const Bubble = ({ line }) => (
  <div className={`flex ${line.role === "user" ? "justify-end" : "justify-start"}`}>
    <p className={`max-w-[85%] rounded-2xl px-3.5 py-2.5 text-[15px] leading-snug ${
      line.role === "user" ? "bg-wt-accent text-white" : "border border-wt-line bg-white text-wt-ink"}`}>
      {line.text}
    </p>
  </div>
);

export const ChatScreen = ({ data, token, adapter, onEnded }) => {
  const [text, setText] = useState("");
  const { lines, prompt } = useCallFeed(adapter, token, onEnded);
  const { quote } = useLiveQuote(token, data.quote);
  const bottom = useRef(null);

  useEffect(() => { bottom.current?.scrollIntoView({ behavior: "smooth" }); }, [lines.length, quote?.version]);

  const send = (e) => {
    e.preventDefault();
    adapter.sendText(text);
    setText("");
  };

  return (
    <div data-testid="chat-screen" className="mx-auto flex min-h-screen max-w-[420px] flex-col px-5 pb-4 pt-5">
      <PortalHeader contractor={data.contractor.name} />
      <div className="mt-4 flex-1 space-y-3">
        {lines.map((l, i) => <Bubble key={i} line={l} />)}
        {quote && <EstimateCard quote={quote} contractor={data.contractor.name} />}
        <div ref={bottom} />
      </div>
      <div className="sticky bottom-0 mt-4 bg-wt-ground pt-2">
        {prompt && (
          <button data-testid="chat-suggestion" onClick={() => setText(prompt)}
            className="mb-2 min-h-[44px] w-full rounded-xl border border-dashed border-wt-line bg-white px-3 py-2 text-left text-[13px] text-wt-muted">
            Suggested reply: <span className="text-wt-ink">{prompt}</span>
          </button>
        )}
        <form onSubmit={send} className="flex gap-2">
          <input data-testid="chat-input" value={text} onChange={(e) => setText(e.target.value)} disabled={!prompt}
            placeholder={prompt ? "Type your reply" : "Waiting for the estimator..."}
            className="h-12 flex-1 rounded-xl border border-wt-line bg-white px-3.5 text-[15px] focus:border-wt-accent focus:outline-none" />
          <button data-testid="chat-send-btn" disabled={!prompt || !text.trim()} aria-label="Send"
            className="grid h-12 w-12 place-items-center rounded-xl bg-wt-accent text-white disabled:opacity-40">
            <Send className="h-5 w-5" />
          </button>
        </form>
        <button data-testid="chat-end-btn" onClick={() => adapter.stop()} className="mt-2 min-h-[44px] w-full text-sm font-semibold text-wt-muted">
          End chat
        </button>
      </div>
    </div>
  );
};
