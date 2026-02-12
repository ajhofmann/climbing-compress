import { VideoListItem } from "@/lib/api";
import {
  matchesNumericRange,
  parseSourceBytesRangeTerm,
  parseSourceBytesComparatorTerm,
  parseOutputBytesRangeTerm,
  parseOutputBytesComparatorTerm,
  parseOutputRangeTerm,
  parseOutputComparatorTerm,
  parseDurationRangeTerm,
  parseDurationComparatorTerm,
  parseFpsRangeTerm,
  parseFpsComparatorTerm,
  parseWidthRangeTerm,
  parseWidthComparatorTerm,
  parseHeightRangeTerm,
  parseHeightComparatorTerm,
  parseAspectRangeTerm,
  parseAspectComparatorTerm,
  parseFrameCountRangeTerm,
  parseFrameCountComparatorTerm,
  parsePixelAreaRangeTerm,
  parsePixelAreaComparatorTerm,
  parseExtensionComparatorTerm,
  parseResolutionRangeTerm,
  parseResolutionComparatorTerm,
  parseNameComparatorTerm,
  parseIdComparatorTerm,
  RECENT_FILTER_SIMPLE_TAG_ALIASES,
} from "./filter-utils";

/**
 * Test whether a single VideoListItem matches a single filter term.
 * This is a pure function with no React dependencies.
 */
export function matchesFilterTerm(item: VideoListItem, term: string): boolean {
  const sourceBytesRange = parseSourceBytesRangeTerm(term);
  if (sourceBytesRange) {
    return matchesNumericRange(item.source_bytes, sourceBytesRange);
  }
  const sourceBytesComparator = parseSourceBytesComparatorTerm(term);
  if (sourceBytesComparator) {
    const { operator, valueBytes } = sourceBytesComparator;
    const sourceBytes = item.source_bytes;
    if (operator === "<") return sourceBytes < valueBytes;
    if (operator === "<=") return sourceBytes <= valueBytes;
    if (operator === ">") return sourceBytes > valueBytes;
    if (operator === ">=") return sourceBytes >= valueBytes;
    if (operator === "!=") return sourceBytes !== valueBytes;
    return sourceBytes === valueBytes;
  }
  const outputBytesRange = parseOutputBytesRangeTerm(term);
  if (outputBytesRange) {
    return matchesNumericRange(item.output_bytes, outputBytesRange);
  }
  const outputBytesComparator = parseOutputBytesComparatorTerm(term);
  if (outputBytesComparator) {
    const { operator, valueBytes } = outputBytesComparator;
    const outputBytesForClip = item.output_bytes;
    if (operator === "<") return outputBytesForClip < valueBytes;
    if (operator === "<=") return outputBytesForClip <= valueBytes;
    if (operator === ">") return outputBytesForClip > valueBytes;
    if (operator === ">=") return outputBytesForClip >= valueBytes;
    if (operator === "!=") return outputBytesForClip !== valueBytes;
    return outputBytesForClip === valueBytes;
  }
  const outputRange = parseOutputRangeTerm(term);
  if (outputRange) {
    return matchesNumericRange(item.output_count, outputRange);
  }
  const outputComparator = parseOutputComparatorTerm(term);
  if (outputComparator) {
    const { operator, value } = outputComparator;
    const outputs = item.output_count;
    if (operator === "<") return outputs < value;
    if (operator === "<=") return outputs <= value;
    if (operator === ">") return outputs > value;
    if (operator === ">=") return outputs >= value;
    if (operator === "!=") return outputs !== value;
    return outputs === value;
  }
  const durationRange = parseDurationRangeTerm(term);
  if (durationRange) {
    return matchesNumericRange(item.info.duration, durationRange);
  }
  const durationComparator = parseDurationComparatorTerm(term);
  if (durationComparator) {
    const { operator, valueSeconds } = durationComparator;
    const duration = item.info.duration;
    if (operator === "<") return duration < valueSeconds;
    if (operator === "<=") return duration <= valueSeconds;
    if (operator === ">") return duration > valueSeconds;
    if (operator === ">=") return duration >= valueSeconds;
    if (operator === "!=") return Math.abs(duration - valueSeconds) >= 0.05;
    return Math.abs(duration - valueSeconds) < 0.05;
  }
  const fpsRange = parseFpsRangeTerm(term);
  if (fpsRange) {
    return matchesNumericRange(item.info.fps, fpsRange);
  }
  const fpsComparator = parseFpsComparatorTerm(term);
  if (fpsComparator) {
    const { operator, value } = fpsComparator;
    const fps = item.info.fps;
    if (operator === "<") return fps < value;
    if (operator === "<=") return fps <= value;
    if (operator === ">") return fps > value;
    if (operator === ">=") return fps >= value;
    if (operator === "!=") return Math.abs(fps - value) >= 0.01;
    return Math.abs(fps - value) < 0.01;
  }
  const widthRange = parseWidthRangeTerm(term);
  if (widthRange) {
    return matchesNumericRange(item.info.width, widthRange);
  }
  const widthComparator = parseWidthComparatorTerm(term);
  if (widthComparator) {
    const { operator, value } = widthComparator;
    const width = item.info.width;
    if (operator === "<") return width < value;
    if (operator === "<=") return width <= value;
    if (operator === ">") return width > value;
    if (operator === ">=") return width >= value;
    if (operator === "!=") return width !== value;
    return width === value;
  }
  const heightRange = parseHeightRangeTerm(term);
  if (heightRange) {
    return matchesNumericRange(item.info.height, heightRange);
  }
  const heightComparator = parseHeightComparatorTerm(term);
  if (heightComparator) {
    const { operator, value } = heightComparator;
    const height = item.info.height;
    if (operator === "<") return height < value;
    if (operator === "<=") return height <= value;
    if (operator === ">") return height > value;
    if (operator === ">=") return height >= value;
    if (operator === "!=") return height !== value;
    return height === value;
  }
  const aspectRange = parseAspectRangeTerm(term);
  if (aspectRange) {
    const aspect = item.info.height > 0 ? item.info.width / item.info.height : 0;
    return matchesNumericRange(aspect, aspectRange);
  }
  const aspectComparator = parseAspectComparatorTerm(term);
  if (aspectComparator) {
    const { operator, value } = aspectComparator;
    const aspect = item.info.height > 0 ? item.info.width / item.info.height : 0;
    if (operator === "<") return aspect < value;
    if (operator === "<=") return aspect <= value;
    if (operator === ">") return aspect > value;
    if (operator === ">=") return aspect >= value;
    if (operator === "!=") return Math.abs(aspect - value) >= 0.005;
    return Math.abs(aspect - value) < 0.005;
  }
  const frameRange = parseFrameCountRangeTerm(term);
  if (frameRange) {
    return matchesNumericRange(item.info.frame_count, frameRange);
  }
  const frameComparator = parseFrameCountComparatorTerm(term);
  if (frameComparator) {
    const { operator, value } = frameComparator;
    const frameCount = item.info.frame_count;
    if (operator === "<") return frameCount < value;
    if (operator === "<=") return frameCount <= value;
    if (operator === ">") return frameCount > value;
    if (operator === ">=") return frameCount >= value;
    if (operator === "!=") return frameCount !== value;
    return frameCount === value;
  }
  const pixelRange = parsePixelAreaRangeTerm(term);
  if (pixelRange) {
    return matchesNumericRange(item.info.width * item.info.height, pixelRange);
  }
  const pixelComparator = parsePixelAreaComparatorTerm(term);
  if (pixelComparator) {
    const { operator, value } = pixelComparator;
    const area = item.info.width * item.info.height;
    if (operator === "<") return area < value;
    if (operator === "<=") return area <= value;
    if (operator === ">") return area > value;
    if (operator === ">=") return area >= value;
    if (operator === "!=") return area !== value;
    return area === value;
  }
  const extensionComparator = parseExtensionComparatorTerm(term);
  if (extensionComparator) {
    const dot = item.filename.lastIndexOf(".");
    const ext = dot >= 0 && dot < item.filename.length - 1
      ? item.filename.slice(dot + 1).toLowerCase()
      : "";
    if (extensionComparator.operator === "!=") return !extensionComparator.values.includes(ext);
    if (extensionComparator.operator === "=") return extensionComparator.values.includes(ext);
    if (extensionComparator.operator === "*=") return ext.includes(extensionComparator.values[0] ?? "");
    if (extensionComparator.operator === "^=") return ext.startsWith(extensionComparator.values[0] ?? "");
    if (extensionComparator.operator === "$=") return ext.endsWith(extensionComparator.values[0] ?? "");
    return false;
  }
  const resolutionRange = parseResolutionRangeTerm(term);
  if (resolutionRange) {
    const sourceWidth = item.info.width;
    const sourceHeight = item.info.height;
    if (resolutionRange.min && (sourceWidth < resolutionRange.min.width || sourceHeight < resolutionRange.min.height)) return false;
    if (resolutionRange.max && (sourceWidth > resolutionRange.max.width || sourceHeight > resolutionRange.max.height)) return false;
    return true;
  }
  const resolutionComparator = parseResolutionComparatorTerm(term);
  if (resolutionComparator) {
    const { operator, width, height } = resolutionComparator;
    const sourceWidth = item.info.width;
    const sourceHeight = item.info.height;
    if (operator === "!=") return sourceWidth !== width || sourceHeight !== height;
    if (operator === "=") return sourceWidth === width && sourceHeight === height;
    if (operator === "<") return sourceWidth < width && sourceHeight < height;
    if (operator === "<=") return sourceWidth <= width && sourceHeight <= height;
    if (operator === ">") return sourceWidth > width && sourceHeight > height;
    if (operator === ">=") return sourceWidth >= width && sourceHeight >= height;
    return false;
  }
  const nameComparator = parseNameComparatorTerm(term);
  if (nameComparator) {
    const fileName = item.filename.toLowerCase();
    if (nameComparator.operator === "!=") return !nameComparator.values.includes(fileName);
    if (nameComparator.operator === "=") return nameComparator.values.includes(fileName);
    if (nameComparator.operator === "*=") return fileName.includes(nameComparator.values[0] ?? "");
    if (nameComparator.operator === "^=") return fileName.startsWith(nameComparator.values[0] ?? "");
    if (nameComparator.operator === "$=") return fileName.endsWith(nameComparator.values[0] ?? "");
    return false;
  }
  const idComparator = parseIdComparatorTerm(term);
  if (idComparator) {
    const id = item.video_id.toLowerCase();
    if (idComparator.operator === "!=") return !idComparator.values.includes(id);
    if (idComparator.operator === "=") return idComparator.values.includes(id);
    if (idComparator.operator === "*=") return id.includes(idComparator.values[0] ?? "");
    if (idComparator.operator === "^=") return id.startsWith(idComparator.values[0] ?? "");
    if (idComparator.operator === "$=") return id.endsWith(idComparator.values[0] ?? "");
    return false;
  }
  if (term.startsWith("#")) {
    const normalizedTerm = (RECENT_FILTER_SIMPLE_TAG_ALIASES[term as keyof typeof RECENT_FILTER_SIMPLE_TAG_ALIASES] ?? term);
    const tag = normalizedTerm.slice(1);
    if (tag === "cached") return item.cached;
    if (tag === "uncached") return !item.cached;
    if (tag === "out") return item.output_count > 0;
    if (tag === "noout") return item.output_count <= 0;
    if (tag === "short") return item.info.duration <= 5;
    if (tag === "long") return item.info.duration > 5;
    if (tag === "portrait") return item.info.height > item.info.width;
    if (tag === "landscape") return item.info.width > item.info.height;
    if (tag === "square") return item.info.width === item.info.height;
  }
  return item.filename.toLowerCase().includes(term);
}
