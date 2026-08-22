import { describe, expect, it } from "vitest";
import { canGenerateDraft, computeMatchLabel, freshnessTag } from "./JobsPage";

describe("computeMatchLabel", () => {
  it("returns none when match is null", () => {
    expect(computeMatchLabel(null)).toEqual({ kind: "none" });
    expect(computeMatchLabel(undefined)).toEqual({ kind: "none" });
  });

  it("returns blocking when blocking_gap is true", () => {
    const result = computeMatchLabel({ met: 0, total: 2, degree_percent: 0, blocking_gap: true });
    expect(result).toEqual({ kind: "blocking" });
  });

  it("returns ok with satisfaction text and percent", () => {
    const result = computeMatchLabel({ met: 3, total: 5, degree_percent: 60, blocking_gap: false });
    expect(result.kind).toBe("ok");
    if (result.kind === "ok") {
      expect(result.text).toContain("满足 3/5");
      expect(result.percent).toBe(60);
    }
  });
});

describe("freshnessTag", () => {
  const now = new Date(2026, 7, 22, 10, 0, 0);

  it("returns 新 for posts within 24 hours", () => {
    const twoHoursAgo = new Date(2026, 7, 22, 8, 0, 0).toISOString();
    expect(freshnessTag(twoHoursAgo, null, now)).toBe("新");
  });

  it("returns 今日 for yesterday posts (age > 24h, previous calendar day)", () => {
    const yesterday = new Date(2026, 7, 21, 9, 0, 0).toISOString();
    expect(freshnessTag(yesterday, null, now)).toBe("今日");
  });

  it("returns empty string for 3-day-old posts", () => {
    const threeDaysAgo = new Date(2026, 7, 19, 10, 0, 0).toISOString();
    expect(freshnessTag(threeDaysAgo, null, now)).toBe("");
  });

  it("falls back to fetchedAt when postedAt is null", () => {
    const recentFetch = new Date(2026, 7, 22, 8, 0, 0).toISOString();
    expect(freshnessTag(null, recentFetch, now)).toBe("新");
  });

  it("returns empty string when both timestamps are null", () => {
    expect(freshnessTag(null, null, now)).toBe("");
    expect(freshnessTag(undefined, undefined, now)).toBe("");
  });
});

describe("canGenerateDraft — 生成简历草稿按钮可见性", () => {
  it("返回 false 当 match_analysis 为 null（无档案或未登录）", () => {
    expect(canGenerateDraft(null)).toBe(false);
    expect(canGenerateDraft(undefined)).toBe(false);
  });

  it("返回 true 当 match_analysis 有内容（已完善档案）", () => {
    expect(canGenerateDraft([])).toBe(true);
    expect(canGenerateDraft([{ requirement: "学历", status: "met", evidence: [] }])).toBe(true);
  });
});
