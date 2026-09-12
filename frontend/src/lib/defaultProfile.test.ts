import { describe, it, expect } from "vitest";
import { clearedProfile, demoProfile, emptyProfile, matchesDemoProfile, profileIsEmpty } from "./defaultProfile";
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

describe("clearedProfile / profileIsEmpty — 一键清空", () => {
  it("clearedProfile：demo 档案清空后九类条目与基本信息全空", () => {
    const cleared = clearedProfile(demoProfile);
    expect(cleared.basics).toEqual({});
    for (const key of [
      "education", "experiences", "projects", "publications", "certificates",
      "skills", "teaching", "awards", "languages",
    ] as const) {
      expect(cleared[key]).toEqual([]);
    }
  });

  it("clearedProfile：保留当前呈现模式（职场人 / 应届生各自保留）", () => {
    expect(clearedProfile(demoProfile).mode).toBe("experienced");
    expect(clearedProfile({ ...demoProfile, mode: "fresh_grad" }).mode).toBe("fresh_grad");
    expect(clearedProfile({ ...demoProfile, mode: undefined }).mode).toBe("experienced");
  });

  it("clearedProfile：basics 是新引用，不与 emptyProfile / 原档案共享", () => {
    const cleared = clearedProfile(demoProfile);
    expect(cleared.basics).not.toBe(emptyProfile.basics);
    expect(cleared.basics).not.toBe(demoProfile.basics);
  });

  it("profileIsEmpty：空档案 → true", () => {
    expect(profileIsEmpty(emptyProfile)).toBe(true);
  });

  it("profileIsEmpty：基本信息任一非空 → false（含纯空白字符串视为空）", () => {
    expect(profileIsEmpty({ ...emptyProfile, basics: { name: "李四" } })).toBe(false);
    expect(profileIsEmpty({ ...emptyProfile, basics: { name: "   " } })).toBe(true);
  });

  it("profileIsEmpty：任一集合有条目 → false", () => {
    const withOneEdu: Profile = {
      ...emptyProfile,
      education: [{ id: "edu-1", school: "某大学" }],
    };
    expect(profileIsEmpty(withOneEdu)).toBe(false);
  });

  it("profileIsEmpty：只差模式/更新时间不算有数据 → true", () => {
    expect(profileIsEmpty({ ...emptyProfile, mode: "fresh_grad", updated_at: "2026-09-12T00:00:00" })).toBe(true);
  });
});
