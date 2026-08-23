import { describe, it, expect } from "vitest";
import { adaptationCoverage, allAdaptedIds } from "./CrawlPage";
import type { Institution } from "../types";

function makeInstitution(overrides: Partial<Institution> = {}): Institution {
  return {
    id: 1,
    name: "测试机构",
    institution_type: "医院",
    region: "北京",
    official_url: "https://example.com",
    listing_url: "https://example.com/jobs",
    crawl_strategy: "fixture",
    enabled: true,
    ...overrides,
  };
}

describe("adaptationCoverage — 机构适配覆盖率计算", () => {
  it("空数组 → adapted=0, total=0", () => {
    expect(adaptationCoverage([])).toEqual({ adapted: 0, total: 0 });
  });

  it("全部已适配 → adapted=total", () => {
    const list = [
      makeInstitution({ id: 1, enabled: true }),
      makeInstitution({ id: 2, enabled: true }),
      makeInstitution({ id: 3, enabled: true }),
    ];
    expect(adaptationCoverage(list)).toEqual({ adapted: 3, total: 3 });
  });

  it("混合状态 → 正确计数", () => {
    const list = [
      makeInstitution({ id: 1, enabled: true }),
      makeInstitution({ id: 2, enabled: false }),
      makeInstitution({ id: 3, enabled: true }),
      makeInstitution({ id: 4, enabled: false }),
      makeInstitution({ id: 5, enabled: false }),
    ];
    expect(adaptationCoverage(list)).toEqual({ adapted: 2, total: 5 });
  });

  it("全部未适配 → adapted=0, total=N", () => {
    const list = [
      makeInstitution({ id: 1, enabled: false }),
      makeInstitution({ id: 2, enabled: false }),
    ];
    expect(adaptationCoverage(list)).toEqual({ adapted: 0, total: 2 });
  });
});

describe("allAdaptedIds — 全选排除未适配机构", () => {
  it("空数组 → 空 Set", () => {
    const result = allAdaptedIds([]);
    expect(result.size).toBe(0);
  });

  it("全部已适配 → 全部选中", () => {
    const list = [
      makeInstitution({ id: 1, enabled: true }),
      makeInstitution({ id: 2, enabled: true }),
    ];
    const result = allAdaptedIds(list);
    expect(result.size).toBe(2);
    expect(result.has(1)).toBe(true);
    expect(result.has(2)).toBe(true);
  });

  it("混合 → 只选中已适配的", () => {
    const list = [
      makeInstitution({ id: 1, enabled: true }),
      makeInstitution({ id: 8, enabled: false }),
      makeInstitution({ id: 11, enabled: true }),
      makeInstitution({ id: 9, enabled: false }),
    ];
    const result = allAdaptedIds(list);
    expect(result.size).toBe(2);
    expect(result.has(1)).toBe(true);
    expect(result.has(11)).toBe(true);
    expect(result.has(8)).toBe(false);
    expect(result.has(9)).toBe(false);
  });

  it("全部未适配 → 空 Set", () => {
    const list = [
      makeInstitution({ id: 8, enabled: false }),
      makeInstitution({ id: 9, enabled: false }),
    ];
    const result = allAdaptedIds(list);
    expect(result.size).toBe(0);
  });
});
