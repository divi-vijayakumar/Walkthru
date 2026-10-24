const Corner = ({ className }) => <span className={`absolute h-7 w-7 border-[#F97316] ${className}`} />;

export const CameraPanel = ({ camera, onToggle, chips }) => (
  <div data-testid="camera-panel" className="relative overflow-hidden rounded-2xl border border-wt-panelLine bg-wt-panel p-4">
    {camera.on && (
      <video ref={camera.videoRef} autoPlay muted playsInline data-testid="camera-video"
        className="absolute inset-0 h-full w-full object-cover opacity-90" />
    )}
    <div className="relative flex items-center justify-between">
      <p className="flex items-center gap-2 text-sm font-semibold text-white">
        <span className={`h-2.5 w-2.5 rounded-full ${camera.on ? "bg-[#2DD4BF]" : "bg-white/40"}`} />
        {camera.on ? "Camera on" : "Camera off"}
      </p>
      <button data-testid="camera-toggle-btn" onClick={onToggle}
        className="min-h-[44px] rounded-full border border-white/25 bg-wt-call/60 px-4 text-sm font-semibold text-white hover:bg-white/10">
        {camera.on ? "Turn off" : "Turn on camera"}
      </button>
    </div>
    <div className="relative mx-6 my-3 flex h-36 items-center justify-center">
      <Corner className="left-0 top-0 rounded-tl-md border-l-[3px] border-t-[3px]" />
      <Corner className="right-0 top-0 rounded-tr-md border-r-[3px] border-t-[3px]" />
      <Corner className="bottom-0 left-0 rounded-bl-md border-b-[3px] border-l-[3px]" />
      <Corner className="bottom-0 right-0 rounded-br-md border-b-[3px] border-r-[3px]" />
      {!camera.on && (
        <p className="px-6 text-center text-sm text-white/70">Your camera is off. Turn it on to show us the space.</p>
      )}
    </div>
    <div className="relative">
      <p className="text-[13px] text-white/70">What I'm seeing</p>
      <div data-testid="seeing-chips" className="mt-2 flex min-h-[32px] flex-wrap gap-2">
        {chips.length === 0 && <span className="text-[13px] text-white/45">{camera.on ? "Looking..." : "Nothing yet"}</span>}
        {chips.map((c) => (
          <span key={c} className="rounded-full bg-white/10 px-3 py-1.5 text-sm font-semibold text-white">{c}</span>
        ))}
      </div>
    </div>
  </div>
);
