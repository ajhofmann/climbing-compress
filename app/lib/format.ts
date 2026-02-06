export const formatAge = (timestamp?: number) => {
  if (timestamp === null || timestamp === undefined) return "";
  if (!Number.isFinite(timestamp)) return "";
  const seconds = Math.max(0, Math.floor(Date.now() / 1000 - timestamp));
  if (seconds < 60) return `${seconds}s`;
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h`;
  const days = Math.floor(hours / 24);
  return `${days}d`;
};

export const formatBytes = (size?: number | null, empty = "") => {
  if (size === null || size === undefined) return empty;
  if (!Number.isFinite(size)) return empty;
  if (size === 0) return "0kb";
  const kb = size / 1024;
  if (kb < 1024) return `${Math.round(kb)}kb`;
  const mb = kb / 1024;
  if (mb < 1024) return `${mb.toFixed(1)}mb`;
  const gb = mb / 1024;
  return `${gb.toFixed(1)}gb`;
};

export const formatOutputType = (outputType: string) => {
  if (outputType === "main") return "render";
  if (outputType === "comparison") return "compare";
  if (outputType === "preview") return "preview";
  return outputType.replace(/_/g, " ");
};

export const formatDuration = (duration?: number | null) => {
  if (duration === null || duration === undefined) return "";
  if (!Number.isFinite(duration)) return "";
  return `${Math.round(duration)}s`;
};

export const formatDurationSeconds = (duration?: number | null) => {
  if (duration === null || duration === undefined) return "";
  if (!Number.isFinite(duration)) return "";
  const seconds = Math.max(0, Math.floor(duration));
  if (seconds < 60) return `${seconds}s`;
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h`;
  const days = Math.floor(hours / 24);
  return `${days}d`;
};
