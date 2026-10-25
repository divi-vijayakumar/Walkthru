import { useEffect, useState } from "react";
import { Mic, MicOff, Video, VideoOff, PhoneOff } from "lucide-react";
import { toast } from "sonner";
import { clock } from "@/shared/format";
import { EqBars } from "@/dashboard/OnCallCard";
import { CameraPanel } from "@/portal/CameraPanel";
import { EstimateCard } from "@/portal/EstimateCard";
import { useCallFeed, useCamera, useLiveQuote } from "@/portal/useCall";

const Control = ({ label, onClick, danger, children, testId }) => (
  <button data-testid={testId} onClick={onClick} className="flex flex-col items-center gap-1.5">
    <span className={`grid h-14 w-14 place-items-center rounded-full transition-colors ${
      danger ? "bg-[#DC2626] text-white hover:bg-[#B91C1C]" : "border border-white/20 bg-wt-panel text-white hover:bg-white/10"}`}>
      {children}
    </span>
    <span className="text-xs text-white/80">{label}</span>
  </button>
);

const AgentRow = ({ caption, agent }) => (
  <div data-testid="agent-row" className="flex items-start gap-3 px-1">
    <span className="grid h-12 w-12 shrink-0 place-items-center rounded-full border-2 border-[#F97316]">
      <EqBars count={4} className="h-5" color="bg-[#F97316]" />
    </span>
    <div className="min-w-0">
      <p className="text-[13px] text-white/70">{!caption || caption.role === "assistant" ? `${agent} is speaking` : "You"}</p>
      <p data-testid="live-caption" className="mt-0.5 text-[17px] font-medium leading-snug text-white">
        {caption ? caption.text : "Connecting..."}
      </p>
    </div>
  </div>
);

export const CallScreen = ({ data, token, adapter, onEnded }) => {
  const [muted, setMuted] = useState(false);
  const [secs, setSecs] = useState(0);
  const { caption } = useCallFeed(adapter, token, onEnded);
  const { quote, chips } = useLiveQuote(token, data.quote);
  const camera = useCamera(token);

  useEffect(() => {
    const id = setInterval(() => setSecs((s) => s + 1), 1000);
    return () => clearInterval(id);
  }, []);

  const toggleCamera = async () => {
    if (camera.on) return camera.stop();
    if (!(await camera.start())) toast.error("Camera not available", { description: "You can keep talking without it." });
  };
  const toggleMute = () => { adapter.setMuted(!muted); setMuted(!muted); };
  const end = () => { camera.on && camera.stop(); adapter.stop(); };

  return (
    <div data-testid="call-screen" className="min-h-screen bg-wt-call">
      <div className="mx-auto flex min-h-screen max-w-[420px] flex-col gap-4 px-4 pb-6 pt-5">
        <div className="flex items-start justify-between">
          <div>
            <p className="text-[17px] font-bold text-white">{data.contractor.name}</p>
            <p className="flex items-center gap-1.5 text-[13px] text-white/75">
              <span className="h-2 w-2 rounded-full bg-[#F97316]" /> AI estimator · recorded
            </p>
          </div>
          <span data-testid="call-timer" className="rounded-full bg-wt-panel px-3 py-1.5 text-sm font-semibold text-white tabular">{clock(secs)}</span>
        </div>
        <CameraPanel camera={camera} onToggle={toggleCamera} chips={chips} />
        <AgentRow caption={caption} agent={data.contractor.agent_name} />
        <EstimateCard quote={quote} contractor={data.contractor.name} />
        <div className="mt-auto flex justify-center gap-10 pt-4">
          <Control testId="call-mute-btn" label={muted ? "Unmute" : "Mute"} onClick={toggleMute}>
            {muted ? <MicOff className="h-5 w-5" /> : <Mic className="h-5 w-5" />}
          </Control>
          <Control testId="call-camera-btn" label="Camera" onClick={toggleCamera}>
            {camera.on ? <VideoOff className="h-5 w-5" /> : <Video className="h-5 w-5" />}
          </Control>
          <Control testId="call-end-btn" label="End" onClick={end} danger>
            <PhoneOff className="h-5 w-5" />
          </Control>
        </div>
      </div>
    </div>
  );
};
