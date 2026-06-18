import { describe, expect, it } from "vitest";
import { evidenceSourceLabel, evidenceStrengthLabel, evidenceStrengthTone } from "./resumeEvidence";

describe("resume evidence helpers", () => {
  it("labels evidence strength without exposing internal vocabulary", () => {
    expect(evidenceStrengthLabel("strong")).toBe("强匹配");
    expect(evidenceStrengthLabel("partial")).toBe("部分匹配");
    expect(evidenceStrengthLabel("weak")).toBe("弱匹配");
    expect(evidenceStrengthTone("strong")).toBe("success");
  });

  it("prefers human-readable source labels over field ids", () => {
    expect(evidenceSourceLabel({ source_label: "科研/项目经历：队列研究", profile_field_id: "proj-1" })).toBe("科研/项目经历：队列研究");
    expect(evidenceSourceLabel({ profile_field_id: "proj-1" })).toBe("proj-1");
  });
});
