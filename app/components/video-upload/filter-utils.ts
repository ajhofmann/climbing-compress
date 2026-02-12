export const SUPPORTED_VIDEO_EXTS = [".mov", ".mp4", ".avi", ".mkv"] as const;
export const RECENT_PREVIEW_LIMIT = 6;
export const RECENT_CURSOR_PAGE_STEP = 5;
export const RECENT_PREF_KEY = "sendit.recentPrefs";
export const RECENT_SORT_MODES = ["recent", "name", "duration", "outputs", "size", "fps", "resolution"] as const;
export const RECENT_FILTER_SIMPLE_TAGS = ["#cached", "#uncached", "#out", "#noout", "#short", "#long", "#portrait", "#landscape", "#square"] as const;
export const RECENT_FILTER_SIMPLE_TAG_ALIASES = {
  "#cache": "#cached",
  "#warm": "#cached",
  "#nocache": "#uncached",
  "#cold": "#uncached",
  "#vertical": "#portrait",
  "#vert": "#portrait",
  "#horizontal": "#landscape",
  "#horiz": "#landscape",
  "#sq": "#square",
} as const;
export const RECENT_FILTER_SIMPLE_TAG_ALIAS_SUGGESTIONS = Object.keys(RECENT_FILTER_SIMPLE_TAG_ALIASES) as (keyof typeof RECENT_FILTER_SIMPLE_TAG_ALIASES)[];
export const RECENT_FILTER_TAG_TEMPLATES = ["#out>=1", "#out=0", "#out!=0", "#out=..0", "#src>3k", "#mb>0b", "#src>10m", "#mb>10m", "#src=2k..", "#dur>5", "#dur<5", "#dur!=5", "#dur>90s", "#dur>1m30s", "#dur=..2", "#ar>=1.3", "#ar=1.3..1.8", "#fc<=30", "#px>=2mp", "#px=1mp..3mp", "#ext=mp4", "#ext=mp4,mov", "#ext*=mp", "#res=1920x1080", "#res>=1920x1080", "#res=1280x720..1920x1080", "#name=clip.mp4", "#name=clip.mp4,other.mp4", "#name*=clip", "#id*=abc", "#id=abc123,def456"] as const;
export const RECENT_COMPARATOR_FAMILIES = ["#out", "#src", "#mb", "#dur", "#fps", "#w", "#h", "#ar", "#fc", "#px", "#res"] as const;
export const RECENT_COMPARATOR_TYPO_FAMILIES = ["#out", "#outputs", "#src", "#source", "#sourcebytes", "#mb", "#render", "#outputbytes", "#dur", "#time", "#duration", "#fps", "#framerate", "#w", "#width", "#h", "#height", "#ar", "#aspect", "#ratio", "#fc", "#frames", "#px", "#pixels", "#mp", "#res", "#resolution", "#ext", "#format", "#name", "#file", "#filename", "#id", "#video", "#videoid", "#vid"] as const;
export const RECENT_RANGE_HINT_TAGS_BY_FAMILY: Record<(typeof RECENT_COMPARATOR_FAMILIES)[number], readonly string[]> = {
  "#out": ["#out=0..2", "#out=..0"],
  "#src": ["#src=2k..4k", "#src=2k.."],
  "#mb": ["#mb=0b..1m", "#mb=..1m"],
  "#dur": ["#dur=1..2", "#dur=..2", "#dur=0:01..0:06"],
  "#fps": ["#fps=24..60", "#fps=..30"],
  "#w": ["#w=720..1920", "#w=..1080"],
  "#h": ["#h=720..1920", "#h=..1920"],
  "#ar": ["#ar=1.3..1.8", "#ar=..1.4"],
  "#fc": ["#fc=25..200", "#fc=..30"],
  "#px": ["#px=1mp..3mp", "#px=..2mp"],
  "#res": ["#res=1280x720..1920x1080", "#res=..1920x1080"],
};
export const RECENT_FILTER_RANGE_SUGGESTIONS = ["#out=0..2", "#out=..0", "#src=2k..4k", "#src=2k..", "#mb=0b..1m", "#mb=..1m", "#dur=1..2", "#dur=..2", "#ar=1.3..1.8", "#ar=..1.4", "#fc=25..200", "#fc=..30", "#px=1mp..3mp", "#px=..2mp", "#res=1280x720..1920x1080", "#res=..1920x1080"] as const;
export const RECENT_FILTER_META_SUGGESTIONS = ["#fps>=24", "#fps<=60", "#fps=24..60", "#w>=1080", "#w=..1080", "#h>=1080", "#h=..1920", "#ar>=1.3", "#ar<=1.8", "#ar=1.3..1.8", "#fc>=25", "#fc<=30", "#fc=25..200", "#px>=2mp", "#px<=4mp", "#px=1mp..3mp", "#res=1920x1080", "#res>=1920x1080", "#res!=1920x1080", "#name=clip.mp4", "#name=clip.mp4,other.mp4", "#name!=clip.mp4", "#name*=clip", "#name^=recent_", "#name$=.mp4", "#id*=abc", "#id^=c9b0", "#id=deadbeef00", "#id=abc123,def456"] as const;
export const RECENT_FILTER_TAGS = [...RECENT_FILTER_SIMPLE_TAGS, ...RECENT_FILTER_TAG_TEMPLATES] as const;
export const RECENT_OUTPUT_HINT_TAGS = ["#out>=1", "#out=0", "#out!=0"] as const;
export const RECENT_STORAGE_HINT_TAGS = ["#src>3k", "#mb>0b", "#src>10m"] as const;
export const RECENT_DURATION_HINT_TAGS = ["#dur>5", "#dur!=5", "#dur>90s", "#dur>1m30s"] as const;
export const RECENT_EXTENSION_HINT_TAGS = ["#ext=mp4", "#ext=mp4,mov", "#ext!=mp4", "#ext*=mp"] as const;
export const RECENT_NAME_HINT_TAGS = ["#name=clip.mp4", "#name=clip.mp4,other.mp4", "#name!=clip.mp4", "#name*=clip"] as const;
export const RECENT_ID_HINT_TAGS = ["#id*=abc", "#id^=c9b0", "#id=deadbeef00", "#id=abc123,def456"] as const;
export const RECENT_VIDEO_META_HINT_TAGS_BY_FAMILY = {
  "#fps": ["#fps>=24", "#fps=24..60"],
  "#w": ["#w>=1080", "#w=..1080"],
  "#h": ["#h>=1080", "#h=..1920"],
  "#ar": ["#ar>=1.3", "#ar=1.3..1.8"],
  "#fc": ["#fc>=25", "#fc=25..200"],
  "#px": ["#px>=2mp", "#px=1mp..3mp"],
  "#res": ["#res=1920x1080", "#res>=1920x1080", "#res!=1920x1080"],
} as const;
export type ComparatorOperator = "<" | "<=" | ">" | ">=" | "=" | "!=";
export type ExtensionComparatorOperator = "=" | "!=" | "*=" | "^=" | "$=";
export type ExtensionComparatorTerm = { operator: ExtensionComparatorOperator; values: string[] };
export type ResolutionComparatorOperator = ComparatorOperator;
export type ResolutionPair = { width: number; height: number };
export type ResolutionRangeFilter = { min: ResolutionPair | null; max: ResolutionPair | null };
export type NameComparatorOperator = "=" | "!=" | "*=" | "^=" | "$=";
export type NameComparatorTerm = { operator: NameComparatorOperator; values: string[] };
export type IdComparatorOperator = "=" | "!=" | "*=" | "^=" | "$=";
export type IdComparatorTerm = { operator: IdComparatorOperator; values: string[] };
export type NumericRangeFilter = { min: number | null; max: number | null };
export type RecentSortMode = (typeof RECENT_SORT_MODES)[number];

export function normalizeComparatorOperator(raw: string): ComparatorOperator | null {
  if (raw === "≤") return "<=";
  if (raw === "≥") return ">=";
  if (raw === "≠") return "!=";
  if (raw === "<=" || raw === "=<") return "<=";
  if (raw === ">=" || raw === "=>") return ">=";
  if (raw === "=" || raw === "==") return "=";
  if (raw === "!=" || raw === "<>") return "!=";
  if (raw === "<" || raw === ">") return raw;
  return null;
}

export function normalizeNumericRange(left: number, right: number): NumericRangeFilter {
  return left <= right ? { min: left, max: right } : { min: right, max: left };
}

export function matchesNumericRange(value: number, range: NumericRangeFilter): boolean {
  if (range.min != null && value < range.min) return false;
  if (range.max != null && value > range.max) return false;
  return true;
}

export function parseDurationLiteralSeconds(raw: string): number | null {
  const value = raw.trim().toLowerCase();
  if (!value) return null;
  if (/^\d+(?:\.\d+)?$/.test(value)) {
    const seconds = Number(value);
    return Number.isFinite(seconds) ? seconds : null;
  }
  const secondsMatch = value.match(/^(\d+(?:\.\d+)?)s$/);
  if (secondsMatch) {
    const seconds = Number(secondsMatch[1]);
    return Number.isFinite(seconds) ? seconds : null;
  }
  const clockMatch = value.match(/^(\d+):(\d{1,2}(?:\.\d+)?)$/);
  if (clockMatch) {
    const minutes = Number(clockMatch[1]);
    const seconds = Number(clockMatch[2]);
    if (!Number.isFinite(minutes) || !Number.isFinite(seconds) || seconds >= 60) return null;
    return minutes * 60 + seconds;
  }
  const clockHmsMatch = value.match(/^(\d+):(\d{1,2}):(\d{1,2}(?:\.\d+)?)$/);
  if (clockHmsMatch) {
    const hours = Number(clockHmsMatch[1]);
    const minutes = Number(clockHmsMatch[2]);
    const seconds = Number(clockHmsMatch[3]);
    if (!Number.isFinite(hours) || !Number.isFinite(minutes) || !Number.isFinite(seconds)) return null;
    if (minutes >= 60 || seconds >= 60) return null;
    return hours * 3600 + minutes * 60 + seconds;
  }
  const hoursMatch = value.match(/^(\d+)h(?:(\d+)m)?(?:(\d+(?:\.\d+)?)s?)?$/);
  if (hoursMatch) {
    const hours = Number(hoursMatch[1]);
    const minutes = hoursMatch[2] ? Number(hoursMatch[2]) : 0;
    const seconds = hoursMatch[3] ? Number(hoursMatch[3]) : 0;
    if (!Number.isFinite(hours) || !Number.isFinite(minutes) || !Number.isFinite(seconds)) return null;
    if (minutes >= 60 || seconds >= 60) return null;
    return hours * 3600 + minutes * 60 + seconds;
  }
  const decimalMinutesMatch = value.match(/^(\d+(?:\.\d+)?)m$/);
  if (decimalMinutesMatch) {
    const minutes = Number(decimalMinutesMatch[1]);
    return Number.isFinite(minutes) ? minutes * 60 : null;
  }
  const minutesMatch = value.match(/^(\d+)m(?:(\d+(?:\.\d+)?)s?)?$/);
  if (!minutesMatch) return null;
  const minutes = Number(minutesMatch[1]);
  const seconds = minutesMatch[2] ? Number(minutesMatch[2]) : 0;
  if (!Number.isFinite(minutes) || !Number.isFinite(seconds)) return null;
  return minutes * 60 + seconds;
}

export function parseDecimalLiteral(raw: string): number | null {
  const token = raw.trim();
  if (!/^\d+(?:\.\d+)?$/.test(token)) return null;
  const value = Number(token);
  return Number.isFinite(value) ? value : null;
}

export function parseIntegerLiteral(raw: string): number | null {
  const token = raw.trim();
  if (!/^\d+$/.test(token)) return null;
  const value = Number(token);
  return Number.isFinite(value) ? value : null;
}

export function parsePixelAreaLiteral(raw: string): number | null {
  const token = raw.trim().toLowerCase();
  const match = token.match(/^(\d+(?:\.\d+)?)(mp|m|k)?$/);
  if (!match) return null;
  const base = Number(match[1]);
  if (!Number.isFinite(base)) return null;
  const unit = match[2] ?? "";
  if (unit === "k") return base * 1_000;
  if (unit === "m" || unit === "mp") return base * 1_000_000;
  return base;
}

export function parseOpenRangeParts(
  leftRaw: string,
  rightRaw: string,
  parseValue: (token: string) => number | null,
): NumericRangeFilter | null {
  const leftToken = leftRaw.trim();
  const rightToken = rightRaw.trim();
  const hasLeft = leftToken.length > 0;
  const hasRight = rightToken.length > 0;
  if (!hasLeft && !hasRight) return null;
  const left = hasLeft ? parseValue(leftToken) : null;
  const right = hasRight ? parseValue(rightToken) : null;
  if ((left != null && !Number.isFinite(left)) || (right != null && !Number.isFinite(right))) return null;
  if (hasLeft && left == null) return null;
  if (hasRight && right == null) return null;
  if (left != null && right != null) return normalizeNumericRange(left, right);
  if (left != null) return { min: left, max: null };
  if (right != null) return { min: null, max: right };
  return null;
}

export function parseOutputComparatorTerm(term: string): { operator: ComparatorOperator; value: number } | null {
  const comparatorMatch = term.match(/^#(?:out|outputs)(<=|=<|>=|=>|!=|<>|==|=|<|>|≤|≥|≠)(\d+)$/);
  if (!comparatorMatch) return null;
  const operator = normalizeComparatorOperator(comparatorMatch[1]);
  if (!operator) return null;
  const value = Number(comparatorMatch[2]);
  if (!Number.isFinite(value)) return null;
  return { operator, value };
}

export function parseOutputRangeTerm(term: string): NumericRangeFilter | null {
  const rangeMatch = term.match(/^#(?:out|outputs)(?:==|=)(.*?)\.\.(.*)$/);
  if (!rangeMatch) return null;
  return parseOpenRangeParts(rangeMatch[1], rangeMatch[2], parseIntegerLiteral);
}

export function parseSourceBytesRangeTerm(term: string): NumericRangeFilter | null {
  const rangeMatch = term.match(/^#(?:src|source|sourcebytes)(?:==|=)(.*?)\.\.(.*)$/);
  if (!rangeMatch) return null;
  return parseOpenRangeParts(rangeMatch[1], rangeMatch[2], parseByteLiteral);
}

export function parseByteLiteral(raw: string): number | null {
  const match = raw.trim().toLowerCase().match(/^(\d+(?:\.\d+)?)(?:\s*)(kib|mib|gib|ki|mi|gi|kb|mb|gb|b|k|m|g)?$/);
  if (!match) return null;
  const amount = Number(match[1]);
  if (!Number.isFinite(amount)) return null;
  const unit = match[2] ?? "b";
  const multiplier = unit === "k" || unit === "kb" || unit === "ki" || unit === "kib"
    ? 1024
    : unit === "m" || unit === "mb" || unit === "mi" || unit === "mib"
      ? 1024 * 1024
      : unit === "g" || unit === "gb" || unit === "gi" || unit === "gib"
        ? 1024 * 1024 * 1024
        : 1;
  return amount * multiplier;
}

export function parseSourceBytesComparatorTerm(term: string): { operator: ComparatorOperator; valueBytes: number } | null {
  const comparatorMatch = term.match(/^#(?:src|source|sourcebytes)(<=|=<|>=|=>|!=|<>|==|=|<|>|≤|≥|≠)(.+)$/);
  if (!comparatorMatch) return null;
  const operator = normalizeComparatorOperator(comparatorMatch[1]);
  if (!operator) return null;
  const valueBytes = parseByteLiteral(comparatorMatch[2]);
  if (valueBytes == null || !Number.isFinite(valueBytes)) return null;
  return { operator, valueBytes };
}

export function parseOutputBytesComparatorTerm(term: string): { operator: ComparatorOperator; valueBytes: number } | null {
  const comparatorMatch = term.match(/^#(?:mb|render|outputbytes)(<=|=<|>=|=>|!=|<>|==|=|<|>|≤|≥|≠)(.+)$/);
  if (!comparatorMatch) return null;
  const operator = normalizeComparatorOperator(comparatorMatch[1]);
  if (!operator) return null;
  const valueBytes = parseByteLiteral(comparatorMatch[2]);
  if (valueBytes == null || !Number.isFinite(valueBytes)) return null;
  return { operator, valueBytes };
}

export function parseOutputBytesRangeTerm(term: string): NumericRangeFilter | null {
  const rangeMatch = term.match(/^#(?:mb|render|outputbytes)(?:==|=)(.*?)\.\.(.*)$/);
  if (!rangeMatch) return null;
  return parseOpenRangeParts(rangeMatch[1], rangeMatch[2], parseByteLiteral);
}

export function parseDurationComparatorTerm(term: string): { operator: ComparatorOperator; valueSeconds: number } | null {
  const comparatorMatch = term.match(/^#(?:dur|time|duration)(<=|=<|>=|=>|!=|<>|==|=|<|>|≤|≥|≠)(.+)$/);
  if (!comparatorMatch) return null;
  const operator = normalizeComparatorOperator(comparatorMatch[1]);
  if (!operator) return null;
  const valueSeconds = parseDurationLiteralSeconds(comparatorMatch[2]);
  if (valueSeconds == null || !Number.isFinite(valueSeconds)) return null;
  return { operator, valueSeconds };
}

export function parseDurationRangeTerm(term: string): NumericRangeFilter | null {
  const rangeMatch = term.match(/^#(?:dur|time|duration)(?:==|=)(.*?)\.\.(.*)$/);
  if (!rangeMatch) return null;
  return parseOpenRangeParts(rangeMatch[1], rangeMatch[2], parseDurationLiteralSeconds);
}

export function parseAspectRatioLiteral(raw: string): number | null {
  const value = raw.trim().toLowerCase();
  if (!value) return null;
  const ratioMatch = value.match(/^(\d+(?:\.\d+)?)\s*:\s*(\d+(?:\.\d+)?)$/);
  if (ratioMatch) {
    const width = Number(ratioMatch[1]);
    const height = Number(ratioMatch[2]);
    if (!Number.isFinite(width) || !Number.isFinite(height) || height <= 0) return null;
    const ratio = width / height;
    return Number.isFinite(ratio) && ratio > 0 ? ratio : null;
  }
  const ratio = parseDecimalLiteral(value);
  if (ratio == null || ratio <= 0) return null;
  return ratio;
}

export function parseAspectComparatorTerm(term: string): { operator: ComparatorOperator; value: number } | null {
  const comparatorMatch = term.match(/^#(?:ar|aspect|ratio)(<=|=<|>=|=>|!=|<>|==|=|<|>|≤|≥|≠)(.+)$/);
  if (!comparatorMatch) return null;
  const operator = normalizeComparatorOperator(comparatorMatch[1]);
  if (!operator) return null;
  const value = parseAspectRatioLiteral(comparatorMatch[2]);
  if (value == null) return null;
  return { operator, value };
}

export function parseAspectRangeTerm(term: string): NumericRangeFilter | null {
  const rangeMatch = term.match(/^#(?:ar|aspect|ratio)(?:==|=)(.*?)\.\.(.*)$/);
  if (!rangeMatch) return null;
  return parseOpenRangeParts(rangeMatch[1], rangeMatch[2], parseAspectRatioLiteral);
}

export function parseFrameCountComparatorTerm(term: string): { operator: ComparatorOperator; value: number } | null {
  const comparatorMatch = term.match(/^#(?:fc|frames)(<=|=<|>=|=>|!=|<>|==|=|<|>|≤|≥|≠)(\d+)$/);
  if (!comparatorMatch) return null;
  const operator = normalizeComparatorOperator(comparatorMatch[1]);
  if (!operator) return null;
  const value = parseIntegerLiteral(comparatorMatch[2]);
  if (value == null) return null;
  return { operator, value };
}

export function parseFrameCountRangeTerm(term: string): NumericRangeFilter | null {
  const rangeMatch = term.match(/^#(?:fc|frames)(?:==|=)(.*?)\.\.(.*)$/);
  if (!rangeMatch) return null;
  return parseOpenRangeParts(rangeMatch[1], rangeMatch[2], parseIntegerLiteral);
}

export function parsePixelAreaComparatorTerm(term: string): { operator: ComparatorOperator; value: number } | null {
  const comparatorMatch = term.match(/^#(?:px|pixels|mp)(<=|=<|>=|=>|!=|<>|==|=|<|>|≤|≥|≠)(.+)$/i);
  if (!comparatorMatch) return null;
  const operator = normalizeComparatorOperator(comparatorMatch[1]);
  if (!operator) return null;
  const value = parsePixelAreaLiteral(comparatorMatch[2]);
  if (value == null || !Number.isFinite(value)) return null;
  return { operator, value };
}

export function parsePixelAreaRangeTerm(term: string): NumericRangeFilter | null {
  const rangeMatch = term.match(/^#(?:px|pixels|mp)(?:==|=)(.*?)\.\.(.*)$/i);
  if (!rangeMatch) return null;
  return parseOpenRangeParts(rangeMatch[1], rangeMatch[2], parsePixelAreaLiteral);
}

export function parseExtensionComparatorTerm(term: string): ExtensionComparatorTerm | null {
  const comparatorMatch = term.match(/^#(?:ext|format)(\*=|\^=|\$=|==|=|!=|<>)([a-z0-9.,|]+)$/i);
  if (!comparatorMatch) return null;
  const operator: ExtensionComparatorOperator = comparatorMatch[1] === "=" || comparatorMatch[1] === "=="
    ? "="
    : comparatorMatch[1] === "!=" || comparatorMatch[1] === "<>"
      ? "!="
      : comparatorMatch[1] === "*=" || comparatorMatch[1] === "^=" || comparatorMatch[1] === "$="
        ? comparatorMatch[1]
        : "=";
  const rawValue = comparatorMatch[2].trim().toLowerCase();
  if (!rawValue) return null;
  if (operator === "=" || operator === "!=") {
    const values = rawValue
      .replace(/\|/g, ",")
      .split(",")
      .map((entry) => entry.trim().replace(/^\./, ""))
      .filter((entry, idx, arr) => entry.length > 0 && arr.indexOf(entry) === idx);
    if (values.length <= 0) return null;
    return { operator, values };
  }
  if (rawValue.includes(",") || rawValue.includes("|")) return null;
  const value = rawValue.replace(/^\./, "");
  if (!value) return null;
  return { operator, values: [value] };
}

export function parseResolutionPairLiteral(raw: string): ResolutionPair | null {
  const match = raw.trim().match(/^(\d{1,5})\s*(?:x|×|\*|:)\s*(\d{1,5})$/i);
  if (!match) return null;
  const width = parseIntegerLiteral(match[1]);
  const height = parseIntegerLiteral(match[2]);
  if (width == null || height == null || width <= 0 || height <= 0) return null;
  return { width, height };
}

export function parseResolutionRangeTerm(term: string): ResolutionRangeFilter | null {
  const rangeMatch = term.match(/^#(?:res|resolution)(?:==|=)(.*?)\.\.(.*)$/i);
  if (!rangeMatch) return null;
  const leftToken = rangeMatch[1].trim();
  const rightToken = rangeMatch[2].trim();
  const hasLeft = leftToken.length > 0;
  const hasRight = rightToken.length > 0;
  if (!hasLeft && !hasRight) return null;
  const left = hasLeft ? parseResolutionPairLiteral(leftToken) : null;
  const right = hasRight ? parseResolutionPairLiteral(rightToken) : null;
  if (hasLeft && !left) return null;
  if (hasRight && !right) return null;
  if (left && right) {
    return {
      min: { width: Math.min(left.width, right.width), height: Math.min(left.height, right.height) },
      max: { width: Math.max(left.width, right.width), height: Math.max(left.height, right.height) },
    };
  }
  if (left) return { min: left, max: null };
  if (right) return { min: null, max: right };
  return null;
}

export function parseResolutionComparatorTerm(term: string): { operator: ResolutionComparatorOperator; width: number; height: number } | null {
  const comparatorMatch = term.match(/^#(?:res|resolution)(<=|=<|>=|=>|!=|<>|==|=|<|>|≤|≥|≠)(.+)$/i);
  if (!comparatorMatch) return null;
  const operator = normalizeComparatorOperator(comparatorMatch[1]);
  if (!operator) return null;
  const value = parseResolutionPairLiteral(comparatorMatch[2]);
  if (!value) return null;
  return { operator, width: value.width, height: value.height };
}

export function parseNameComparatorTerm(term: string): NameComparatorTerm | null {
  const comparatorMatch = term.match(/^#(?:name|file|filename)(\*=|\^=|\$=|==|=|!=|<>)(.+)$/i);
  if (!comparatorMatch) return null;
  const operator: NameComparatorOperator = comparatorMatch[1] === "=" || comparatorMatch[1] === "=="
    ? "="
    : comparatorMatch[1] === "!=" || comparatorMatch[1] === "<>"
      ? "!="
      : comparatorMatch[1] === "*=" || comparatorMatch[1] === "^=" || comparatorMatch[1] === "$="
        ? comparatorMatch[1]
        : "=";
  const rawValue = comparatorMatch[2].trim().toLowerCase();
  if (/^[<>=!≤≥≠]/.test(rawValue)) return null;
  if (!rawValue) return null;
  if (operator === "=" || operator === "!=") {
    const values = rawValue
      .replace(/\|/g, ",")
      .split(",")
      .map((entry) => entry.trim())
      .filter((entry, idx, arr) => entry.length > 0 && arr.indexOf(entry) === idx);
    if (values.length <= 0) return null;
    return { operator, values };
  }
  return { operator, values: [rawValue] };
}

export function parseIdComparatorTerm(term: string): IdComparatorTerm | null {
  const comparatorMatch = term.match(/^#(?:id|video|videoid|vid)(\*=|\^=|\$=|==|=|!=|<>)([a-z0-9,_|-]+)$/i);
  if (!comparatorMatch) return null;
  const operator: IdComparatorOperator = comparatorMatch[1] === "=" || comparatorMatch[1] === "=="
    ? "="
    : comparatorMatch[1] === "!=" || comparatorMatch[1] === "<>"
      ? "!="
      : comparatorMatch[1] === "*=" || comparatorMatch[1] === "^=" || comparatorMatch[1] === "$="
        ? comparatorMatch[1]
        : "=";
  const rawValue = comparatorMatch[2].trim().toLowerCase();
  if (!rawValue) return null;
  if (operator === "=" || operator === "!=") {
    const values = rawValue
      .replace(/\|/g, ",")
      .split(",")
      .map((entry) => entry.trim())
      .filter((entry, idx, arr) => entry.length > 0 && arr.indexOf(entry) === idx);
    if (values.length <= 0) return null;
    return { operator, values };
  }
  return { operator, values: [rawValue] };
}

export function parseFpsComparatorTerm(term: string): { operator: ComparatorOperator; value: number } | null {
  const comparatorMatch = term.match(/^#(?:fps|framerate)(<=|=<|>=|=>|!=|<>|==|=|<|>|≤|≥|≠)(\d+(?:\.\d+)?)$/);
  if (!comparatorMatch) return null;
  const operator = normalizeComparatorOperator(comparatorMatch[1]);
  if (!operator) return null;
  const value = parseDecimalLiteral(comparatorMatch[2]);
  if (value == null) return null;
  return { operator, value };
}

export function parseFpsRangeTerm(term: string): NumericRangeFilter | null {
  const rangeMatch = term.match(/^#(?:fps|framerate)(?:==|=)(.*?)\.\.(.*)$/);
  if (!rangeMatch) return null;
  return parseOpenRangeParts(rangeMatch[1], rangeMatch[2], parseDecimalLiteral);
}

export function parseWidthComparatorTerm(term: string): { operator: ComparatorOperator; value: number } | null {
  const comparatorMatch = term.match(/^#(?:w|width)(<=|=<|>=|=>|!=|<>|==|=|<|>|≤|≥|≠)(\d+)$/);
  if (!comparatorMatch) return null;
  const operator = normalizeComparatorOperator(comparatorMatch[1]);
  if (!operator) return null;
  const value = parseIntegerLiteral(comparatorMatch[2]);
  if (value == null) return null;
  return { operator, value };
}

export function parseWidthRangeTerm(term: string): NumericRangeFilter | null {
  const rangeMatch = term.match(/^#(?:w|width)(?:==|=)(.*?)\.\.(.*)$/);
  if (!rangeMatch) return null;
  return parseOpenRangeParts(rangeMatch[1], rangeMatch[2], parseIntegerLiteral);
}

export function parseHeightComparatorTerm(term: string): { operator: ComparatorOperator; value: number } | null {
  const comparatorMatch = term.match(/^#(?:h|height)(<=|=<|>=|=>|!=|<>|==|=|<|>|≤|≥|≠)(\d+)$/);
  if (!comparatorMatch) return null;
  const operator = normalizeComparatorOperator(comparatorMatch[1]);
  if (!operator) return null;
  const value = parseIntegerLiteral(comparatorMatch[2]);
  if (value == null) return null;
  return { operator, value };
}

export function parseHeightRangeTerm(term: string): NumericRangeFilter | null {
  const rangeMatch = term.match(/^#(?:h|height)(?:==|=)(.*?)\.\.(.*)$/);
  if (!rangeMatch) return null;
  return parseOpenRangeParts(rangeMatch[1], rangeMatch[2], parseIntegerLiteral);
}

export function remapVideoMetaAliasForTarget(tag: string, targetTerm: string): string {
  const normalizedTarget = targetTerm.toLowerCase();
  if (normalizedTarget.startsWith("#pixels") && tag.startsWith("#px")) {
    return `#pixels${tag.slice(3)}`;
  }
  if (normalizedTarget.startsWith("#mp") && tag.startsWith("#px")) {
    return `#mp${tag.slice(3)}`;
  }
  if (normalizedTarget.startsWith("#videoid") && tag.startsWith("#id")) {
    return `#videoid${tag.slice(3)}`;
  }
  if (normalizedTarget.startsWith("#outputbytes") && tag.startsWith("#mb")) {
    return `#outputbytes${tag.slice(3)}`;
  }
  if (normalizedTarget.startsWith("#sourcebytes") && tag.startsWith("#src")) {
    return `#sourcebytes${tag.slice(4)}`;
  }
  if (normalizedTarget.startsWith("#render") && tag.startsWith("#mb")) {
    return `#render${tag.slice(3)}`;
  }
  if (normalizedTarget.startsWith("#outputs") && tag.startsWith("#out")) {
    return `#outputs${tag.slice(4)}`;
  }
  if (normalizedTarget.startsWith("#source") && tag.startsWith("#src")) {
    return `#source${tag.slice(4)}`;
  }
  if (normalizedTarget.startsWith("#video") && tag.startsWith("#id")) {
    return `#video${tag.slice(3)}`;
  }
  if (normalizedTarget.startsWith("#vid") && tag.startsWith("#id")) {
    return `#vid${tag.slice(3)}`;
  }
  if (normalizedTarget.startsWith("#duration") && tag.startsWith("#dur")) {
    return `#duration${tag.slice(4)}`;
  }
  if (normalizedTarget.startsWith("#time") && tag.startsWith("#dur")) {
    return `#time${tag.slice(4)}`;
  }
  if (normalizedTarget.startsWith("#aspect") && tag.startsWith("#ar")) {
    return `#aspect${tag.slice(3)}`;
  }
  if (normalizedTarget.startsWith("#ratio") && tag.startsWith("#ar")) {
    return `#ratio${tag.slice(3)}`;
  }
  if (normalizedTarget.startsWith("#filename") && tag.startsWith("#name")) {
    return `#filename${tag.slice(5)}`;
  }
  if (normalizedTarget.startsWith("#file") && tag.startsWith("#name")) {
    return `#file${tag.slice(5)}`;
  }
  if (normalizedTarget.startsWith("#resolution") && tag.startsWith("#res")) {
    return `#resolution${tag.slice(4)}`;
  }
  if (normalizedTarget.startsWith("#format") && tag.startsWith("#ext")) {
    return `#format${tag.slice(4)}`;
  }
  if (normalizedTarget.startsWith("#framerate") && tag.startsWith("#fps")) {
    return `#framerate${tag.slice(4)}`;
  }
  if (normalizedTarget.startsWith("#width") && tag.startsWith("#w")) {
    return `#width${tag.slice(2)}`;
  }
  if (normalizedTarget.startsWith("#height") && tag.startsWith("#h")) {
    return `#height${tag.slice(2)}`;
  }
  if (normalizedTarget.startsWith("#frames") && tag.startsWith("#fc")) {
    return `#frames${tag.slice(3)}`;
  }
  return tag;
}

export function normalizeRecentFilterTerms(sourceTerms: string[]): string[] {
  const dedupedTerms: string[] = [];
  for (const token of sourceTerms) {
    const lower = token.toLowerCase();
    const isTagToken = lower.startsWith("#") || lower.startsWith("-#") || lower.startsWith("!#") || lower.startsWith("+#");
    if (isTagToken && dedupedTerms.some((entry) => entry.toLowerCase() === lower)) continue;
    dedupedTerms.push(token);
  }
  return dedupedTerms;
}

export function parseRecentFilterQuery(source: string): string[] {
  const terms: string[] = [];
  const text = source.trim();
  let buffer = "";
  let activeQuote: "'" | '"' | null = null;
  let escaped = false;
  for (const char of text) {
    if (activeQuote) {
      if (escaped) {
        buffer += char;
        escaped = false;
        continue;
      }
      if (char === "\\") {
        escaped = true;
        continue;
      }
      if (char === activeQuote) {
        activeQuote = null;
        continue;
      }
      buffer += char;
      continue;
    }
    if (char === "'" || char === '"') {
      const canStartQuotedSegment = buffer.length === 0
        || buffer === "-"
        || buffer === "!"
        || buffer === "+"
        || /[=><!^*$]$/.test(buffer);
      if (canStartQuotedSegment) {
        activeQuote = char;
        continue;
      }
    }
    if (/\s/.test(char)) {
      if (buffer.length > 0) {
        terms.push(buffer);
        buffer = "";
      }
      continue;
    }
    buffer += char;
  }
  if (escaped) buffer += "\\";
  if (buffer.length > 0) terms.push(buffer);
  return terms;
}

export function stringifyRecentFilterTerms(sourceTerms: string[]): string {
  return sourceTerms
    .filter((term) => term.length > 0)
    .map((term) => {
      const shouldQuote = /\s/.test(term) || term.startsWith("'") || term.startsWith('"');
      if (!shouldQuote) return term;
      const escaped = term.replace(/\\/g, "\\\\").replace(/"/g, '\\"');
      return `"${escaped}"`;
    })
    .join(" ");
}

export function withExcludePrefix(term: string, prefix: "-" | "!" | null): string {
  if (!prefix) return term;
  const normalizedTerm = term.startsWith("-") || term.startsWith("!")
    ? term.slice(1)
    : term;
  return `${prefix}${normalizedTerm}`;
}

export function withIncludePrefix(term: string, includePrefix: boolean): string {
  if (!includePrefix) return term;
  const normalizedTerm = term.startsWith("+") || term.startsWith("-") || term.startsWith("!")
    ? term.slice(1)
    : term;
  return `+${normalizedTerm}`;
}

export function applyParsedTermPrefix(term: string, excludePrefix: "-" | "!" | null, includePrefix: boolean): string {
  if (excludePrefix) return withExcludePrefix(term, excludePrefix);
  return withIncludePrefix(term, includePrefix);
}

export function levenshteinDistance(left: string, right: string): number {
  if (left === right) return 0;
  if (left.length === 0) return right.length;
  if (right.length === 0) return left.length;
  const prev = Array.from({ length: right.length + 1 }, (_, idx) => idx);
  for (let i = 0; i < left.length; i += 1) {
    const curr = [i + 1];
    for (let j = 0; j < right.length; j += 1) {
      const cost = left[i] === right[j] ? 0 : 1;
      curr[j + 1] = Math.min(
        curr[j] + 1,
        prev[j + 1] + 1,
        prev[j] + cost,
      );
    }
    for (let j = 0; j < curr.length; j += 1) prev[j] = curr[j];
  }
  return prev[right.length];
}

export function formatBytesShort(bytes: number | null) {
  if (bytes == null || !Number.isFinite(bytes)) return "?";
  const safe = Math.max(0, Math.round(bytes));
  if (safe < 1024) return `${safe}b`;
  if (safe < 1024 * 1024) return `${(safe / 1024).toFixed(safe < 10 * 1024 ? 1 : 0)}k`;
  if (safe < 1024 * 1024 * 1024) return `${(safe / (1024 * 1024)).toFixed(safe < 10 * 1024 * 1024 ? 1 : 0)}m`;
  return `${(safe / (1024 * 1024 * 1024)).toFixed(safe < 10 * 1024 * 1024 * 1024 ? 1 : 0)}g`;
}

export function formatBytesVerbose(bytes: number | null) {
  if (bytes == null || !Number.isFinite(bytes)) return "unknown size";
  const safe = Math.max(0, bytes);
  if (safe < 1024) return `${safe.toFixed(0)} B`;
  if (safe < 1024 * 1024) return `${(safe / 1024).toFixed(1)} KB`;
  if (safe < 1024 * 1024 * 1024) return `${(safe / (1024 * 1024)).toFixed(1)} MB`;
  return `${(safe / (1024 * 1024 * 1024)).toFixed(2)} GB`;
}
