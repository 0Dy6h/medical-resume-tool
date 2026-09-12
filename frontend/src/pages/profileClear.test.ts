import { describe, it, expect } from "vitest";
import { collapsedSetForMode, freshEditingState } from "./ProfilePage";

describe("collapsedSetForMode — 模式默认折叠集合（切换/演示/清空共用）", () => {
  it("应届生布局：仅工作/实习经历默认折叠", () => {
    expect([...collapsedSetForMode("fresh_grad")]).toEqual(["experiences"]);
  });

  it("职场人布局：无默认折叠", () => {
    expect(collapsedSetForMode("experienced").size).toBe(0);
  });

  it("每次调用返回全新实例，互不共享引用", () => {
    const a = collapsedSetForMode("fresh_grad");
    const b = collapsedSetForMode("fresh_grad");
    expect(a).not.toBe(b);
    a.add("education");
    expect(b.has("education")).toBe(false);
  });
});

describe("freshEditingState — 一键清空复位的编辑态初始包", () => {
  it("全部字段为初始空值", () => {
    const fresh = freshEditingState();
    expect(fresh.preview).toBeNull();
    expect(fresh.importError).toBeNull();
    expect(fresh.selectedKeys.size).toBe(0);
    expect(fresh.assignedBlocks).toEqual({});
    expect(fresh.blockAssignSelections).toEqual({});
  });

  it("每次调用返回全新引用，Set/对象不共享", () => {
    const a = freshEditingState();
    const b = freshEditingState();
    expect(a.selectedKeys).not.toBe(b.selectedKeys);
    expect(a.assignedBlocks).not.toBe(b.assignedBlocks);
    expect(a.blockAssignSelections).not.toBe(b.blockAssignSelections);
  });
});
