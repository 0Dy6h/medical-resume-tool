import { describe, it, expect } from "vitest";
import { usernameValidationError } from "./LoginPage";

describe("usernameValidationError — 注册用户名校验（口径同后端 RegisterPayload）", () => {
  it("空/纯空白 → 请填写用户名", () => {
    expect(usernameValidationError("")).toBe("请填写用户名");
    expect(usernameValidationError("   ")).toBe("请填写用户名");
  });

  it("含空白字符（半角/全角/制表）→ 用户名不能包含空格", () => {
    expect(usernameValidationError("has space")).toBe("用户名不能包含空格");
    expect(usernameValidationError("用户 名")).toBe("用户名不能包含空格");
    expect(usernameValidationError("全角\u3000空格")).toBe("用户名不能包含空格");
    expect(usernameValidationError("tab\tuser")).toBe("用户名不能包含空格");
  });

  it("长度越界 → 用户名需 2-32 个字符", () => {
    expect(usernameValidationError("a")).toBe("用户名需 2-32 个字符");
    expect(usernameValidationError("a".repeat(33))).toBe("用户名需 2-32 个字符");
  });

  it("中文/英文/下划线合法 → null（首尾空白按 UI trim 后的值校验）", () => {
    expect(usernameValidationError("中文用户名")).toBeNull();
    expect(usernameValidationError("trial_b6_r1")).toBeNull();
    expect(usernameValidationError("  alice  ")).toBeNull();
    expect(usernameValidationError(" leading")).toBeNull();
  });
});
