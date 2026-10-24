export const Panel = ({ title, icon: Icon, action, children, testId, className = "" }) => (
  <section data-testid={testId} className={`rounded-xl border border-zinc-800 bg-[#18181b] ${className}`}>
    <header className="flex items-center justify-between gap-3 border-b border-zinc-800 px-5 py-3.5">
      <div className="flex items-center gap-2">
        {Icon && <Icon className="h-4 w-4 text-orange-500" />}
        <h2 className="text-base font-semibold tracking-tight text-zinc-100">{title}</h2>
      </div>
      {action}
    </header>
    <div className="p-5">{children}</div>
  </section>
);

export const EmptyState = ({ icon: Icon, title, body }) => (
  <div className="flex flex-col items-center justify-center rounded-lg border border-dashed border-zinc-700/80 px-6 py-12 text-center">
    <span className="grid h-11 w-11 place-items-center rounded-full bg-zinc-800 text-zinc-400">
      <Icon className="h-5 w-5" />
    </span>
    <p className="mt-4 text-sm font-semibold text-zinc-200">{title}</p>
    <p className="mt-1 max-w-xs text-xs leading-relaxed text-zinc-500">{body}</p>
  </div>
);
