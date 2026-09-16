import { afterEach, describe, expect, it, vi } from "vitest";
import { api, getToken, setToken, setUnauthorizedHandler, parseContentDispositionFilename, SessionChangedError, UnauthorizedError } from "./api";

describe("session responses", () => {
  afterEach(() => {
    setUnauthorizedHandler(null);
    vi.unstubAllGlobals();
  });

  function storage(token: string | null = "account-a") {
    let current = token;
    vi.stubGlobal("localStorage", {
      getItem: () => current,
      setItem: (_: string, value: string) => { current = value; },
      removeItem: () => { current = null; }
    });
  }

  it("a delayed 401 from account A cannot log account B out", async () => {
    storage();
    const logout = vi.fn();
    setUnauthorizedHandler(logout);
    let respond!: (value: Response) => void;
    vi.stubGlobal("fetch", vi.fn(() => new Promise<Response>((resolve) => { respond = resolve; })));
    const pending = api.profile();
    setToken("account-b");
    respond(new Response('{"detail":"expired"}', { status: 401 }));
    await expect(pending).rejects.toBeInstanceOf(UnauthorizedError);
    expect(getToken()).toBe("account-b");
    expect(logout).not.toHaveBeenCalled();
  });

  it("rejects the previous account's successful response after a switch", async () => {
    storage();
    let respond!: (value: Response) => void;
    vi.stubGlobal("fetch", vi.fn(() => new Promise<Response>((resolve) => { respond = resolve; })));
    const pending = api.profile();
    setToken("account-b");
    respond(new Response('{"basics":{"name":"account-a-private"}}'));
    await expect(pending).rejects.toBeInstanceOf(SessionChangedError);
  });

  it("checks the account again after response body decoding", async () => {
    storage();
    let decode!: (value: string) => void;
    const response = new Response();
    response.text = () => new Promise((resolve) => { decode = resolve; });
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(response));
    const pending = api.profile();
    await vi.waitFor(() => expect(decode).toBeTypeOf("function"));
    setToken("account-b");
    decode('{"basics":{"name":"account-a-private"}}');
    await expect(pending).rejects.toBeInstanceOf(SessionChangedError);
  });

  it("invalidates the current expired token once", async () => {
    storage();
    const logout = vi.fn();
    setUnauthorizedHandler(logout);
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(null, { status: 401 })));
    await expect(api.profile()).rejects.toBeInstanceOf(UnauthorizedError);
    expect(getToken()).toBeNull();
    expect(logout).toHaveBeenCalledTimes(1);
  });
});

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
