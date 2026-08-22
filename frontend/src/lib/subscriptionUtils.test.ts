import { describe, expect, it } from "vitest";
import {
  formatLastPushed,
  validateSubscriptionForm,
  subscriptionSubtitle,
  countMaintenanceInstitutions,
  hasBroadKeywordWarning
} from "./subscriptionUtils";
import type { Subscription } from "../types";

function makeSubscription(overrides: Partial<Subscription> = {}): Subscription {
  return {
    id: 1,
    name: "测试订阅",
    keyword: "内科",
    institution_ids: [1],
    institution_statuses: [{ id: 1, name: "测试医院", is_maintenance: false }],
    new_count: 0,
    last_checked_at: "2026-08-20T10:00:00.000Z",
    last_pushed_at: "2026-08-20T10:00:00.000Z",
    is_empty_30d: false,
    created_at: "2026-08-01T00:00:00.000Z",
    ...overrides
  };
}

describe("formatLastPushed", () => {
  it("returns '刚刚' for timestamps within 1 minute", () => {
    const now = new Date("2026-08-20T10:00:30.000Z");
    expect(formatLastPushed("2026-08-20T10:00:00.000Z", now)).toBe("刚刚");
  });

  it("returns 'X 分钟前' for timestamps within 1 hour", () => {
    const now = new Date("2026-08-20T10:15:00.000Z");
    expect(formatLastPushed("2026-08-20T10:00:00.000Z", now)).toBe("15 分钟前");
  });

  it("returns 'X 小时前' for timestamps within 24 hours", () => {
    const now = new Date("2026-08-20T15:00:00.000Z");
    expect(formatLastPushed("2026-08-20T10:00:00.000Z", now)).toBe("5 小时前");
  });

  it("returns date string for older timestamps", () => {
    const now = new Date("2026-08-22T10:00:00.000Z");
    const result = formatLastPushed("2026-08-20T10:00:00.000Z", now);
    // Should not be the "刚刚/分钟/小时" format
    expect(result).not.toContain("刚刚");
    expect(result).not.toContain("分钟前");
    expect(result).not.toContain("小时前");
  });

  it("handles null input gracefully", () => {
    expect(formatLastPushed(null)).toBe("未推送");
  });

  it("handles invalid date strings", () => {
    expect(formatLastPushed("not-a-date")).toBe("not-a-date");
  });
});

describe("validateSubscriptionForm", () => {
  const valid = { name: "内科岗位", keyword: "内科", institutionIds: [1, 2] };

  it("passes for valid input", () => {
    expect(validateSubscriptionForm(valid)).toBe("");
  });

  it("rejects name too short", () => {
    expect(validateSubscriptionForm({ ...valid, name: "A" })).toContain("2 个字符");
  });

  it("rejects name too long", () => {
    expect(validateSubscriptionForm({ ...valid, name: "A".repeat(31) })).toContain("30 个字符");
  });

  it("rejects empty keyword", () => {
    expect(validateSubscriptionForm({ ...valid, keyword: "" })).toContain("关键词");
  });

  it("rejects keyword too long", () => {
    expect(validateSubscriptionForm({ ...valid, keyword: "A".repeat(51) })).toContain("50 个字符");
  });

  it("rejects empty institution list", () => {
    expect(validateSubscriptionForm({ ...valid, institutionIds: [] })).toContain("至少选择 1 家");
  });

  it("rejects more than 12 institutions", () => {
    const ids = Array.from({ length: 13 }, (_, i) => i + 1);
    expect(validateSubscriptionForm({ ...valid, institutionIds: ids })).toContain("12 家");
  });

  it("trims whitespace before validating name and keyword", () => {
    expect(validateSubscriptionForm({ ...valid, name: "  内科  ", keyword: "  内科  " })).toBe("");
  });
});

describe("subscriptionSubtitle", () => {
  it("shows 30-day empty message when applicable", () => {
    const sub = makeSubscription({ new_count: 0, is_empty_30d: true });
    expect(subscriptionSubtitle(sub)).toBe("近 30 天无新职位");
  });

  it("shows count and last pushed time normally", () => {
    const sub = makeSubscription({
      new_count: 5,
      is_empty_30d: false,
      last_pushed_at: "2026-08-20T10:00:00.000Z"
    });
    const result = subscriptionSubtitle(sub);
    expect(result).toContain("5 条新职位");
    expect(result).toContain("上次推送");
  });

  it("shows 未推送 when last_pushed_at is null", () => {
    const sub = makeSubscription({
      new_count: 3,
      last_pushed_at: null
    });
    const result = subscriptionSubtitle(sub);
    expect(result).toContain("未推送");
  });
});

describe("countMaintenanceInstitutions", () => {
  it("counts institutions in maintenance", () => {
    const statuses = [
      { is_maintenance: false },
      { is_maintenance: true },
      { is_maintenance: true }
    ];
    expect(countMaintenanceInstitutions(statuses)).toBe(2);
  });

  it("returns 0 for empty list", () => {
    expect(countMaintenanceInstitutions([])).toBe(0);
  });
});

describe("hasBroadKeywordWarning", () => {
  it("detects broad keyword warning", () => {
    expect(hasBroadKeywordWarning("关键词过宽，命中 100 条职位")).toBe(true);
  });

  it("returns false for no warning", () => {
    expect(hasBroadKeywordWarning(null)).toBe(false);
    expect(hasBroadKeywordWarning(undefined)).toBe(false);
    expect(hasBroadKeywordWarning("")).toBe(false);
  });

  it("returns false for other warnings", () => {
    expect(hasBroadKeywordWarning("其他类型的警告")).toBe(false);
  });
});
