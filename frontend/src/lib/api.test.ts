import { describe, expect, it } from "vitest";
import { parseContentDispositionFilename } from "./api";

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
