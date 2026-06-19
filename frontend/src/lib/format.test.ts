import { describe, expect, it } from "vitest";
import { formatDate, isDemoStrategy, maxCount } from "./format";

describe("format helpers", () => {
  it("keeps missing dates scannable", () => {
    expect(formatDate(null)).toBe("未记录");
  });

  it("guards empty chart domains", () => {
    expect(maxCount([])).toBe(1);
  });

  it("flags fixture sources as demo data", () => {
    expect(isDemoStrategy("fixture")).toBe(true);
    expect(isDemoStrategy("nfyy")).toBe(false);
    expect(isDemoStrategy(null)).toBe(false);
  });
});
