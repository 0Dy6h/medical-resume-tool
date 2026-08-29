import { afterEach, describe, expect, it, vi } from "vitest";
import { api, parseContentDispositionFilename } from "./api";

describe("request — 204/空响应体处理", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  function stubFetch(status: number, body?: string) {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(body ?? null, { status }),
    );
    vi.stubGlobal("fetch", fetchMock);
    vi.stubGlobal("localStorage", {
      getItem: () => null,
      setItem: () => {},
      removeItem: () => {},
    });
    return fetchMock;
  }

  it("删除订阅返回 204 无响应体时不抛错（回归：不再报 JSON 解析错误）", async () => {
    const fetchMock = stubFetch(204);
    await expect(api.deleteSubscription(7)).resolves.toBeUndefined();
    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(init.method).toBe("DELETE");
  });

  it("200 但空响应体同样安全返回 undefined", async () => {
    stubFetch(200, "");
    await expect(api.deleteSubscription(7)).resolves.toBeUndefined();
  });

  it("正常 JSON 响应仍被解析", async () => {
    stubFetch(200, JSON.stringify([{ id: 1 }]));
    await expect(api.subscriptions()).resolves.toEqual([{ id: 1 }]);
  });
});


describe("parseContentDispositionFilename", () => {
  it("parses plain filename", () => {
    const header = 'attachment; filename="resume-1.docx"';
    expect(parseContentDispositionFilename(header)).toBe("resume-1.docx");
  });

  it("parses filename without quotes", () => {
    const header = "attachment; filename=resume-1.docx";
    expect(parseContentDispositionFilename(header)).toBe("resume-1.docx");
  });

  it("parses RFC 5987 filename* with percent-encoded Chinese", () => {
    const encoded = encodeURIComponent("张三-内科医师-简历-20260824.docx");
    const header = `attachment; filename="resume.docx"; filename*=UTF-8''${encoded}`;
    expect(parseContentDispositionFilename(header)).toBe("张三-内科医师-简历-20260824.docx");
  });

  it("prefers filename* over filename when both present", () => {
    const encoded = encodeURIComponent("李四-简历.pdf");
    const header = `attachment; filename="resume.pdf"; filename*=UTF-8''${encoded}`;
    expect(parseContentDispositionFilename(header)).toBe("李四-简历.pdf");
  });

  it("returns null when neither filename nor filename* present", () => {
    expect(parseContentDispositionFilename("attachment")).toBeNull();
    expect(parseContentDispositionFilename(null)).toBeNull();
    expect(parseContentDispositionFilename("")).toBeNull();
  });

  it("handles filename* with invalid percent-encoding gracefully", () => {
    const header = "attachment; filename*=UTF-8''%E5%BC%A0%E4%B8%89.docx";
    const result = parseContentDispositionFilename(header);
    expect(result).toBe("张三.docx");
  });
});
