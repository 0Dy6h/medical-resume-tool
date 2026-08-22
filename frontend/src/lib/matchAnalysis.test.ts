import { describe, expect, it } from "vitest";
import { findingTone, findingLabel } from "./matchAnalysis";

describe("findingTone", () => {
  it("maps met to success", () => {
    expect(findingTone("met")).toBe("success");
  });

  it("maps partial to working", () => {
    expect(findingTone("partial")).toBe("working");
  });

  it("maps blocking to danger", () => {
    expect(findingTone("blocking")).toBe("danger");
  });

  it("maps unmet to danger", () => {
    expect(findingTone("unmet")).toBe("danger");
  });
});

describe("findingLabel", () => {
  it("labels met", () => {
    expect(findingLabel("met")).toBe("已满足");
  });

  it("labels partial", () => {
    expect(findingLabel("partial")).toBe("部分满足");
  });

  it("labels blocking", () => {
    expect(findingLabel("blocking")).toBe("阻塞性差距");
  });

  it("labels unmet", () => {
    expect(findingLabel("unmet")).toBe("不满足");
  });
});
