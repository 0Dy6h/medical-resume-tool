import { describe, it, expect } from "vitest";
import {
  formatDeleteWarning,
  formatOverlapWarning,
  shouldShowDeleteWarning,
  shouldShowOverlapWarning,
} from "./profileChecks";
import type { FieldReferenceResult, OverlapCheckResult } from "./profileChecks";

describe("shouldShowDeleteWarning", () => {
  it("returns false when count is 0", () => {
    const result: FieldReferenceResult = { field_id: "edu-1", count: 0, draft_ids: [] };
    expect(shouldShowDeleteWarning(result)).toBe(false);
  });

  it("returns true when count is 1", () => {
    const result: FieldReferenceResult = { field_id: "edu-1", count: 1, draft_ids: [1] };
    expect(shouldShowDeleteWarning(result)).toBe(true);
  });

  it("returns true when count is greater than 1", () => {
    const result: FieldReferenceResult = { field_id: "edu-1", count: 3, draft_ids: [1, 2, 3] };
    expect(shouldShowDeleteWarning(result)).toBe(true);
  });
});

describe("formatDeleteWarning", () => {
  it("includes the count in the warning text", () => {
    expect(formatDeleteWarning(1)).toBe(
      "该记录已被用于生成 1 份简历草稿，删除后相关草稿的证据链将断裂"
    );
  });

  it("handles multiple drafts", () => {
    expect(formatDeleteWarning(3)).toBe(
      "该记录已被用于生成 3 份简历草稿，删除后相关草稿的证据链将断裂"
    );
  });

  it("handles zero (edge case)", () => {
    expect(formatDeleteWarning(0)).toBe(
      "该记录已被用于生成 0 份简历草稿，删除后相关草稿的证据链将断裂"
    );
  });
});

describe("shouldShowOverlapWarning", () => {
  it("returns false when overlap is false", () => {
    const result: OverlapCheckResult = { overlap: false, items: [] };
    expect(shouldShowOverlapWarning(result)).toBe(false);
  });

  it("returns true when overlap is true", () => {
    const result: OverlapCheckResult = {
      overlap: true,
      items: [{ id: "edu-1" }, { id: "edu-2" }],
    };
    expect(shouldShowOverlapWarning(result)).toBe(true);
  });

  it("returns true when overlap is true even with empty items", () => {
    const result: OverlapCheckResult = { overlap: true, items: [] };
    expect(shouldShowOverlapWarning(result)).toBe(true);
  });
});

describe("formatOverlapWarning", () => {
  it("returns the correct warning text", () => {
    expect(formatOverlapWarning()).toBe(
      "检测到可能与已有记录重叠的经历，是否继续添加？"
    );
  });
});
