import { describe, it, expect } from "vitest";
import { demoProfile, emptyProfile, matchesDemoProfile } from "./defaultProfile";
import type { Profile } from "../types";

describe("matchesDemoProfile — 演示数据签名识别（B4 防呆）", () => {
  it("示例档案本身 → true", () => {
    expect(matchesDemoProfile(demoProfile)).toBe(true);
  });

  it("空档案 → false", () => {
    expect(matchesDemoProfile(emptyProfile)).toBe(false);
  });

  it("姓名被替换 → false（横幅与保存拦截随之解除）", () => {
    const modified: Profile = {
      ...demoProfile,
      basics: { ...demoProfile.basics, name: "张三" },
    };
    expect(matchesDemoProfile(modified)).toBe(false);
  });

  it("电话被替换 → false", () => {
    const modified: Profile = {
      ...demoProfile,
      basics: { ...demoProfile.basics, phone: "139-1111-2222" },
    };
    expect(matchesDemoProfile(modified)).toBe(false);
  });

  it("邮箱被替换 → false", () => {
    const modified: Profile = {
      ...demoProfile,
      basics: { ...demoProfile.basics, email: "zhangsan@example.com" },
    };
    expect(matchesDemoProfile(modified)).toBe(false);
  });

  it("真实用户档案 → false", () => {
    const real: Profile = {
      ...emptyProfile,
      basics: { name: "李四", phone: "138-1234-5678", email: "lisi@example.com" },
    };
    expect(matchesDemoProfile(real)).toBe(false);
  });

  it("演示签名中有空值（部分清除）→ false，不因空串相等而误判", () => {
    const cleared: Profile = {
      ...demoProfile,
      basics: { ...demoProfile.basics, email: "" },
    };
    expect(matchesDemoProfile(cleared)).toBe(false);
  });
});
