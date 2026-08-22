import { describe, it, expect } from "vitest";
import { flattenReviewItems, computeDraftStatus, reviewTone, filterExportSections } from "./ResumePage";
import type { ResumeSection } from "../types";

const sampleSections: ResumeSection[] = [
  {
    id: "identity",
    title: "个人信息",
    items: [
      { text: "林晓" },
      { text: "电话：13800000000" },
    ],
  },
  {
    id: "education",
    title: "教育背景",
    items: [
      { text: "复旦大学 / 硕士", profile_field_id: "edu-1", evidence_level: "matched" },
      { text: "第二大学 / 学士", profile_field_id: "edu-2", evidence_level: "supporting" },
    ],
  },
  {
    id: "gaps",
    title: "投递前需补充确认",
    items: [{ text: "未找到SCI论文证据" }],
  },
];

describe("review mode progress — 第 X/N 项", () => {
  it("flattens all items across sections for step-by-step review", () => {
    const items = flattenReviewItems(sampleSections);
    expect(items.length).toBe(5);
    expect(items[0]).toEqual({
      sectionId: "identity",
      sectionTitle: "个人信息",
      itemIndex: 0,
      text: "林晓",
    });
    expect(items[2].sectionId).toBe("education");
    expect(items[2].profile_field_id).toBe("edu-1");
    expect(items[4].sectionId).toBe("gaps");
  });

  it("progress display is 第 1/5 at start and 第 5/5 at end", () => {
    const items = flattenReviewItems(sampleSections);
    expect(`第 1/${items.length} 项`).toBe("第 1/5 项");
    expect(`第 ${items.length}/${items.length} 项`).toBe("第 5/5 项");
  });
});

describe("review colored cards by evidence strength", () => {
  const evidence = [
    { profile_field_id: "edu-1", evidence_strength: "strong", matched_terms: ["学历"] },
  ];

  it("green for strong evidence or matched level", () => {
    expect(reviewTone({ profile_field_id: "edu-1", evidence_level: "matched" }, evidence)).toBe("green");
  });

  it("yellow for supporting level", () => {
    expect(reviewTone({ profile_field_id: "edu-2", evidence_level: "supporting" }, evidence)).toBe("yellow");
  });

  it("red when no matching evidence", () => {
    const identityItem = { text: "林晓" };
    expect(reviewTone(identityItem, evidence)).toBe("red");
  });
});

describe("computed draft status", () => {
  it("draft when no items have decisions", () => {
    expect(computeDraftStatus(sampleSections)).toBe("draft");
  });

  it("draft when only some items have decisions", () => {
    const partial = sampleSections.map((s, si) => ({
      ...s,
      items: s.items.map((i, ii) =>
        si === 0 && ii === 0 ? { ...i, decision: "adopt" as const } : i,
      ),
    }));
    expect(computeDraftStatus(partial)).toBe("draft");
  });

  it("reviewed when all items have decisions", () => {
    const decided = sampleSections.map((s) => ({
      ...s,
      items: s.items.map((i) => ({ ...i, decision: "adopt" as const })),
    }));
    expect(computeDraftStatus(decided)).toBe("reviewed");
  });
});

describe("完成审阅 — all items become non-pending", () => {
  it("completing review sets undecided items to adopt", () => {
    const withSomeDecisions = sampleSections.map((s, si) => ({
      ...s,
      items: s.items.map((i, ii) =>
        si === 1 && ii === 0 ? { ...i, decision: "edit" as const } : i,
      ),
    }));
    // Simulate "完成审阅": items without decision get "adopt"
    const completed = withSomeDecisions.map((s) => ({
      ...s,
      items: s.items.map((i) => ({ ...i, decision: i.decision ?? ("adopt" as const) })),
    }));
    expect(computeDraftStatus(completed)).toBe("reviewed");
    for (const section of completed) {
      for (const item of section.items) {
        expect(item.decision).toBeDefined();
      }
    }
    // The edit decision is preserved
    expect(completed[1].items[0].decision).toBe("edit");
  });
});

describe("remove filtering for export", () => {
  it("filters out items marked decision=remove", () => {
    const withRemoval = sampleSections.map((s, si) => ({
      ...s,
      items: s.items.map((i, ii) =>
        si === 1 && ii === 0 ? { ...i, decision: "remove" as const } : i,
      ),
    }));
    const filtered = filterExportSections(withRemoval);
    const eduSection = filtered.find((s) => s.id === "education")!;
    expect(eduSection.items.length).toBe(1);
    expect(eduSection.items[0].profile_field_id).toBe("edu-2");
  });

  it("keeps items without decision (backward compatible)", () => {
    const filtered = filterExportSections(sampleSections);
    expect(filtered[0].items.length).toBe(2);
    expect(filtered[1].items.length).toBe(2);
  });

  it("keeps items with adopt and edit decisions", () => {
    const withDecisions = sampleSections.map((s, si) => ({
      ...s,
      items: s.items.map((i, ii) => ({
        ...i,
        decision:
          si === 0 && ii === 0
            ? ("adopt" as const)
            : si === 1 && ii === 0
              ? ("edit" as const)
              : undefined,
      })),
    }));
    const filtered = filterExportSections(withDecisions);
    expect(filtered[0].items.length).toBe(2);
    expect(filtered[1].items.length).toBe(2);
  });
});
