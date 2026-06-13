export const renderHistoryStyles = {
  wrap: "mt-3 border border-cyan-500/20 rounded bg-[var(--panel-bg)]/40 p-3",
  header: "flex items-center justify-between gap-2 mb-2",
  title: "text-sm font-pixel uppercase tracking-widest text-cyan-200",
  actions: "flex items-center gap-2",
  button: "text-sm font-pixel text-cyan-300 hover:text-white disabled:text-text-muted disabled:opacity-35 disabled:cursor-not-allowed",
  timelineRail: "overflow-x-auto pb-1",
  timelineTrack: "flex items-stretch gap-2.5 min-w-max",
  card: "w-[320px] rounded border border-cyan-500/25 bg-black/20 p-3 flex flex-col gap-2",
  cardActive: "border-cyan-300 shadow-[0_0_0_1px_rgba(0,229,255,0.7),0_0_14px_rgba(0,229,255,0.28)]",
} as const;
