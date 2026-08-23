import { describe, it, expect } from "vitest";
import { importExtractionEmpty, buildManualAssignment } from "./ProfilePage";
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

describe("buildManualAssignment — 未归类原文手动归类", () => {
  it("education → 主字段 school", () => {
    const item = buildManualAssignment("education", "复旦大学");
    expect(item).not.toBeNull();
    expect(item!.school).toBe("复旦大学");
  });

  it("experiences → 主字段 organization", () => {
    const item = buildManualAssignment("experiences", "上海某三甲医院");
    expect(item).not.toBeNull();
    expect(item!.organization).toBe("上海某三甲医院");
  });

  it("projects → 主字段 name", () => {
    const item = buildManualAssignment("projects", "慢病队列随访项目");
    expect(item).not.toBeNull();
    expect(item!.name).toBe("慢病队列随访项目");
  });

  it("publications → 主字段 title", () => {
    const item = buildManualAssignment("publications", "公共卫生数据分析研究");
    expect(item).not.toBeNull();
    expect(item!.title).toBe("公共卫生数据分析研究");
  });

  it("teaching → 主字段 course", () => {
    const item = buildManualAssignment("teaching", "流行病学");
    expect(item).not.toBeNull();
    expect(item!.course).toBe("流行病学");
  });

  it("awards → 主字段 name", () => {
    const item = buildManualAssignment("awards", "教学优秀奖");
    expect(item).not.toBeNull();
    expect(item!.name).toBe("教学优秀奖");
  });

  it("certificates → 主字段 name", () => {
    const item = buildManualAssignment("certificates", "大学英语六级");
    expect(item).not.toBeNull();
    expect(item!.name).toBe("大学英语六级");
  });

  it("skills → 主字段 name", () => {
    const item = buildManualAssignment("skills", "SPSS");
    expect(item).not.toBeNull();
    expect(item!.name).toBe("SPSS");
  });

  it("languages → 主字段 name", () => {
    const item = buildManualAssignment("languages", "英语");
    expect(item).not.toBeNull();
    expect(item!.name).toBe("英语");
  });

  it("含前后空白和换行的文本 → trim 后写入主字段，原文内容不改写", () => {
    const raw = "  复旦大学\n临床医学\n硕士  ";
    const item = buildManualAssignment("education", raw);
    expect(item).not.toBeNull();
    expect(item!.school).toBe(raw.trim());
    expect(item!.school).not.toBe(raw);
  });

  it("未知 collection → null", () => {
    expect(buildManualAssignment("unknown_collection", "某文本")).toBeNull();
  });

  it("数组/area 字段初始化为 []，普通字段为 ''", () => {
    const item = buildManualAssignment("education", "复旦大学");
    expect(item).not.toBeNull();
    // area 字段 → []
    expect(item!.highlights).toEqual([]);
    // 普通字段 → ""
    expect(item!.degree).toBe("");
    expect(item!.major).toBe("");
    expect(item!.start).toBe("");
    expect(item!.end).toBe("");
  });

  it("函数内不生成 id，由调用方负责", () => {
    const item = buildManualAssignment("skills", "Python");
    expect(item).not.toBeNull();
    expect(item!.id).toBeUndefined();
  });
});
