import { describe, it, expect } from "vitest";
import { flattenReviewItems, computeDraftStatus, reviewTone, filterExportSections, exportBlock, readPendingDraftId, PENDING_DRAFT_KEY, isUnlinkedReviewItem, shouldResetDraftOnJobChange, reviewCompletion, unlinkedExportCount, mismatchNoticeFromError } from "./ResumePage";
import type { ResumeSection } from "../types";

describe("shouldResetDraftOnJobChange — 切岗时草稿上下文必须跟随选择器", () => {
  it("草稿属于其他岗位 → 需清除（禁止显示岗位 B 却导出岗位 A 草稿）", () => {
    expect(shouldResetDraftOnJobChange(2, { job_id: 1 })).toBe(true);
  });

  it("草稿就属于目标岗位 → 保留", () => {
    expect(shouldResetDraftOnJobChange(2, { job_id: 2 })).toBe(false);
  });

  it("无草稿或岗位未选中 → 不需要清除", () => {
    expect(shouldResetDraftOnJobChange(2, null)).toBe(false);
    expect(shouldResetDraftOnJobChange("", { job_id: 1 })).toBe(false);
  });
});

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

describe("完成审阅 — 不再自动全采纳（B3）", () => {
  const withSomeDecisions: ResumeSection[] = sampleSections.map((s, si) => ({
    ...s,
    items: s.items.map((i, ii) =>
      si === 1 && ii === 0 ? { ...i, decision: "edit" as const } : i,
    ),
  }));

  it("存在未决策条目 → blocked，给出数量并定位第一项索引", () => {
    const result = reviewCompletion(withSomeDecisions);
    expect(result.kind).toBe("blocked");
    if (result.kind === "blocked") {
      expect(result.pending).toBe(4);
      expect(result.firstPendingIndex).toBe(0);
    }
  });

  it("blocked 时草稿保持 draft 状态 —— 未决策项不会被静默置为 adopt", () => {
    // 模拟新版 completeReview：sections 原样保存，不补 decision。
    const afterAttemptedComplete = withSomeDecisions;
    expect(computeDraftStatus(afterAttemptedComplete)).toBe("draft");
    expect(afterAttemptedComplete[0].items[0].decision).toBeUndefined();
  });

  it("全部条目已有决策 → complete", () => {
    const decided = sampleSections.map((s) => ({
      ...s,
      items: s.items.map((i) => ({ ...i, decision: "adopt" as const })),
    }));
    expect(reviewCompletion(decided)).toEqual({ kind: "complete" });
  });
});

describe("unlinkedExportCount — 投递版无证据条目统计（B3）", () => {
  it("全部正文条目绑定档案证据 → 0（身份/缺口区块天然不计入）", () => {
    expect(unlinkedExportCount(sampleSections)).toBe(0);
  });

  it("正文区块存在无 profile_field_id 条目 → 计入", () => {
    const withUnlinked: ResumeSection[] = sampleSections.map((s, si) => ({
      ...s,
      items: si === 1
        ? [{ text: "手动添加的成果", profile_field_id: "edu-1" }, { text: "自定义经历" }, { text: "另一条自定义" }]
        : s.items,
    }));
    expect(unlinkedExportCount(withUnlinked)).toBe(2);
  });

  it("decision=remove 的无证据条目不计入（不会随导出）", () => {
    const withRemoved: ResumeSection[] = sampleSections.map((s, si) => ({
      ...s,
      items: si === 1
        ? [{ text: "自定义经历", decision: "remove" as const }, { text: "保留的自定义" }]
        : s.items,
    }));
    expect(unlinkedExportCount(withRemoved)).toBe(1);
  });

  it("gaps 区块条目不计入", () => {
    const withGapOnly: ResumeSection[] = [
      { id: "gaps", title: "投递前需补充确认", items: [{ text: "未找到SCI论文证据" }] },
    ];
    expect(unlinkedExportCount(withGapOnly)).toBe(0);
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

describe("exportBlock — frontend export guard", () => {
  it("returns proceed when all items have decisions", () => {
    const reviewed = sampleSections.map((s) => ({
      ...s,
      items: s.items.map((i) => ({ ...i, decision: "adopt" as const })),
    }));
    expect(exportBlock(reviewed)).toEqual({ kind: "proceed" });
  });

  it("returns confirm with pending count when no items have decisions", () => {
    const result = exportBlock(sampleSections);
    expect(result.kind).toBe("confirm");
    if (result.kind === "confirm") {
      expect(result.pending).toBe(5);
    }
  });

  it("returns confirm with correct pending count when some items have decisions", () => {
    const partial = sampleSections.map((s, si) => ({
      ...s,
      items: s.items.map((i, ii) =>
        si === 0 && ii === 0 ? { ...i, decision: "adopt" as const } : i,
      ),
    }));
    const result = exportBlock(partial);
    expect(result.kind).toBe("confirm");
    if (result.kind === "confirm") {
      expect(result.pending).toBe(4);
    }
  });
});

describe("readPendingDraftId — 待加载草稿 ID 读取", () => {
  it("返回 null 当存储中没有 pending key", () => {
    const storage = { getItem: (key: string) => null };
    expect(readPendingDraftId(storage)).toBeNull();
  });

  it("返回数字 ID 当存储中有合法的数字字符串", () => {
    const storage = { getItem: (key: string) => (key === PENDING_DRAFT_KEY ? "42" : null) };
    expect(readPendingDraftId(storage)).toBe(42);
  });

  it("返回 null 当值为空字符串", () => {
    const storage = { getItem: (key: string) => "" };
    expect(readPendingDraftId(storage)).toBeNull();
  });

  it("返回 null 当值不是数字", () => {
    const storage = { getItem: (key: string) => "abc" };
    expect(readPendingDraftId(storage)).toBeNull();
  });

  it("返回 null 当值为 0 或负数", () => {
    expect(readPendingDraftId({ getItem: () => "0" })).toBeNull();
    expect(readPendingDraftId({ getItem: () => "-5" })).toBeNull();
  });
});

describe("isUnlinkedReviewItem — 无档案证据关联判定", () => {
  it("identity 区块条目排除 → false", () => {
    expect(isUnlinkedReviewItem({ text: "林晓" }, "identity")).toBe(false);
  });

  it("target 区块条目排除 → false", () => {
    expect(isUnlinkedReviewItem({ text: "应聘科研助理" }, "target")).toBe(false);
  });

  it("gaps 区块条目排除 → false", () => {
    expect(isUnlinkedReviewItem({ text: "未找到SCI论文证据" }, "gaps")).toBe(false);
  });

  it("集合区块无 profile_field_id → true", () => {
    expect(isUnlinkedReviewItem({ text: "自定义经历" }, "experiences")).toBe(true);
  });

  it("集合区块有空 profile_field_id → true", () => {
    expect(isUnlinkedReviewItem({ text: "自定义经历", profile_field_id: "" }, "experiences")).toBe(true);
  });

  it("集合区块有 profile_field_id → false", () => {
    expect(isUnlinkedReviewItem({ text: "科研助理", profile_field_id: "exp-1" }, "experiences")).toBe(false);
  });

  it("decision 为 remove 的条目排除 → false", () => {
    expect(isUnlinkedReviewItem({ text: "自定义经历", decision: "remove" }, "experiences")).toBe(false);
  });

  it("标题为「投递前需补充确认」的区块排除 → false", () => {
    expect(isUnlinkedReviewItem({ text: "待确认项", sectionTitle: "投递前需补充确认" }, "custom")).toBe(false);
  });
});


describe("mismatchNoticeFromError — P0-2 阻断错误转常驻提示", () => {
  it("学历硬阻断的 422 文案 → 返回提示（非 toast 死胡同）", () => {
    const msg = "您的档案与该岗位的要求差距较大，建议关注其他更匹配的职位";
    expect(mismatchNoticeFromError(msg)).toBe(msg);
  });

  it("普通错误（网络/未填履历）→ 返回 null，维持 toast 行为", () => {
    expect(mismatchNoticeFromError("请先填写或导入履历内容")).toBeNull();
    expect(mismatchNoticeFromError("Request failed: 500")).toBeNull();
  });
});
