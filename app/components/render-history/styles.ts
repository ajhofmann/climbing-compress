export const renderHistoryStyles = {
  wrap: "mt-2 border border-cyan-500/20 rounded bg-panel/40 p-2",
  header: "flex items-center justify-between gap-2 mb-2",
  title: "text-[10px] font-pixel uppercase tracking-widest text-cyan-200",
  actions: "flex items-center gap-1",
  button: "text-[9px] font-pixel text-cyan-300 hover:text-white disabled:text-text-muted disabled:opacity-35 disabled:cursor-not-allowed",
  timelineRail: "overflow-x-auto pb-1",
  timelineTrack: "flex items-stretch gap-2 min-w-max",
  card: "w-[290px] rounded border border-cyan-500/25 bg-black/20 p-2 flex flex-col gap-1.5",
  cardActive: "border-cyan-300 shadow-[0_0_0_1px_rgba(0,229,255,0.7),0_0_14px_rgba(0,229,255,0.28)]",
} as const;

