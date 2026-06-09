import { describe, expect, it } from "vitest";
import { formatDate, maxCount } from "./format";

describe("format helpers", () => {
  it("keeps missing dates scannable", () => {
    expect(formatDate(null)).toBe("未记录");
  });

  it("guards empty chart domains", () => {
    expect(maxCount([])).toBe(1);
  });
});
