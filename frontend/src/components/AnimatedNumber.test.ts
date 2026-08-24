import { describe, it, expect } from "vitest";
import { easeOutCubic, lerp, formatNumber } from "./AnimatedNumber";

describe("easeOutCubic", () => {
  it("returns 0 when t = 0", () => {
    expect(easeOutCubic(0)).toBe(0);
  });

  it("returns 1 when t = 1", () => {
    expect(easeOutCubic(1)).toBe(1);
  });

  it("returns values in (0, 1) for t in (0, 1)", () => {
    const testValues = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9];
    for (const t of testValues) {
      const v = easeOutCubic(t);
      expect(v).toBeGreaterThan(0);
      expect(v).toBeLessThan(1);
    }
  });

  it("is monotonically increasing", () => {
    let prev = -1;
    for (let t = 0; t <= 1; t += 0.05) {
      const v = easeOutCubic(t);
      expect(v).toBeGreaterThanOrEqual(prev);
      prev = v;
    }
  });

  it("produces correct cubic ease-out value at t=0.5", () => {
    // easeOutCubic(t) = 1 - (1-t)^3
    // At t=0.5: 1 - 0.5^3 = 1 - 0.125 = 0.875
    expect(easeOutCubic(0.5)).toBeCloseTo(0.875, 10);
  });
});

describe("lerp", () => {
  it("returns a when t = 0", () => {
    expect(lerp(10, 20, 0)).toBe(10);
  });

  it("returns b when t = 1", () => {
    expect(lerp(10, 20, 1)).toBe(20);
  });

  it("returns midpoint when t = 0.5", () => {
    expect(lerp(10, 20, 0.5)).toBe(15);
  });

  it("handles negative numbers", () => {
    expect(lerp(-10, 10, 0.5)).toBe(0);
  });

  it("handles decimals", () => {
    expect(lerp(0, 1, 0.33)).toBeCloseTo(0.33, 10);
  });

  it("handles same a and b", () => {
    expect(lerp(5, 5, 0.7)).toBe(5);
  });
});

describe("formatNumber", () => {
  it("formats integer with 0 decimals", () => {
    expect(formatNumber(42, 0)).toBe("42");
  });

  it("formats number with decimals", () => {
    expect(formatNumber(3.14159, 2)).toBe("3.14");
  });

  it("pads decimals with zeros", () => {
    expect(formatNumber(5, 2)).toBe("5.00");
  });

  it("adds prefix", () => {
    expect(formatNumber(100, 0, "¥")).toBe("¥100");
  });

  it("adds suffix", () => {
    expect(formatNumber(50, 0, undefined, "%")).toBe("50%");
  });

  it("adds both prefix and suffix", () => {
    expect(formatNumber(99.9, 1, "$", " USD")).toBe("$99.9 USD");
  });

  it("handles zero", () => {
    expect(formatNumber(0, 0)).toBe("0");
  });

  it("handles negative numbers", () => {
    expect(formatNumber(-100, 0)).toBe("-100");
  });
});
