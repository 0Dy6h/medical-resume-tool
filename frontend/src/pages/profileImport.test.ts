import { describe, it, expect } from "vitest";
import { importExtractionEmpty } from "./ProfilePage";
import type { ProfileImportResult } from "../types";

function emptyResult(): ProfileImportResult {
  return {
    education: [],
    experiences: [],
    projects: [],
    publications: [],
    certificates: [],
    skills: [],
    teaching: [],
    awards: [],
    languages: [],
    warnings: [],
  };
}

describe("importExtractionEmpty — 导入解析失败判定", () => {
  it("全空 → true", () => {
    expect(importExtractionEmpty(emptyResult())).toBe(true);
  });

  it("仅 basics 有值 → false", () => {
    const result = emptyResult();
    result.basics = { name: "张三" };
    expect(importExtractionEmpty(result)).toBe(false);
  });

  it("仅 review_items 有值 → false", () => {
    const result = emptyResult();
    result.review_items = [
      { collection: "education", item: {}, source_text: "某文本", confidence: 0.5, warnings: [] },
    ];
    expect(importExtractionEmpty(result)).toBe(false);
  });

  it("仅 unassigned_blocks 有值 → true", () => {
    const result = emptyResult();
    result.unassigned_blocks = [{ text: "未归类文本", reason: "无法匹配" }];
    expect(importExtractionEmpty(result)).toBe(true);
  });

  it("education 有值 → false", () => {
    const result = emptyResult();
    result.education = [{ id: "edu-1", school: "复旦大学" }];
    expect(importExtractionEmpty(result)).toBe(false);
  });

  it("basics 全为空字符串 → true", () => {
    const result = emptyResult();
    result.basics = { name: "", phone: "  " };
    expect(importExtractionEmpty(result)).toBe(true);
  });
});
