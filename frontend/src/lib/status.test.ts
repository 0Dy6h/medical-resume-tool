import { describe, expect, it } from "vitest";
import { statusLabel, statusTone } from "./status";

describe("status helpers", () => {
  it("labels partial crawl runs as partially completed", () => {
    expect(statusLabel("partial")).toBe("部分完成");
    expect(statusTone("partial")).toBe("working");
  });

  it("keeps the older completed_with_errors status compatible", () => {
    expect(statusLabel("completed_with_errors")).toBe("部分完成");
    expect(statusTone("completed_with_errors")).toBe("working");
  });

  it("labels parser review states for quality dashboards", () => {
    expect(statusLabel("review")).toBe("需复核");
    expect(statusTone("review")).toBe("danger");
    expect(statusLabel("watch")).toBe("观察");
    expect(statusTone("watch")).toBe("working");
    expect(statusLabel("stable")).toBe("稳定");
    expect(statusTone("stable")).toBe("success");
  });

  it("labels user job workflow states", () => {
    expect(statusLabel("preparing")).toBe("准备中");
    expect(statusTone("preparing")).toBe("working");
    expect(statusLabel("applied")).toBe("已投递");
    expect(statusTone("applied")).toBe("success");
  });
});
