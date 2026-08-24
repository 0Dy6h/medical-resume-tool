import { describe, expect, it } from "vitest";
import { foldTags } from "./jobUtils";

describe("foldTags", () => {
  it("returns all tags when count <= maxVisible", () => {
    expect(foldTags(["a", "b"])).toEqual({
      visible: ["a", "b"],
      hidden: [],
      remaining: 0,
    });
  });

  it("folds excess tags into hidden array", () => {
    expect(foldTags(["a", "b", "c", "d"])).toEqual({
      visible: ["a", "b"],
      hidden: ["c", "d"],
      remaining: 2,
    });
  });

  it("handles empty tags", () => {
    expect(foldTags([])).toEqual({ visible: [], hidden: [], remaining: 0 });
  });

  it("handles single tag", () => {
    expect(foldTags(["a"])).toEqual({
      visible: ["a"],
      hidden: [],
      remaining: 0,
    });
  });

  it("respects custom maxVisible", () => {
    expect(foldTags(["a", "b", "c"], 1)).toEqual({
      visible: ["a"],
      hidden: ["b", "c"],
      remaining: 2,
    });
  });

  it("returns correct remaining count", () => {
    const result = foldTags(["a", "b", "c", "d", "e"]);
    expect(result.remaining).toBe(3);
    expect(result.hidden).toEqual(["c", "d", "e"]);
  });
});
