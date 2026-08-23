import { describe, it, expect } from "vitest";
import { shouldShowAllParserWarning, formatGeneratedAt } from "./AnalyticsPage";
import type { ParserQuality } from "../types";

function makeParser(overrides: Partial<ParserQuality> = {}): ParserQuality {
  return {
    parser_name: "nfyy",
    jobs: 5,
    low_confidence_jobs: 0,
    attachment_sourced_jobs: 0,
    failed_attachment_events: 0,
    average_confidence: 0.9,
    review_status: "stable",
    ...overrides,
  };
}

describe("shouldShowAllParserWarning", () => {
  it("returns false when parser list is empty", () => {
    expect(shouldShowAllParserWarning([])).toBe(false);
  });

  it("returns true when all parsers have review_status 'review'", () => {
    const parsers = [
      makeParser({ parser_name: "nfyy", review_status: "review" }),
      makeParser({ parser_name: "z2hospital", review_status: "review" }),
    ];
    expect(shouldShowAllParserWarning(parsers)).toBe(true);
  });

  it("returns false when some parsers are not 'review'", () => {
    const parsers = [
      makeParser({ parser_name: "nfyy", review_status: "review" }),
      makeParser({ parser_name: "z2hospital", review_status: "watch" }),
    ];
    expect(shouldShowAllParserWarning(parsers)).toBe(false);
  });

  it("returns false when no parser is 'review'", () => {
    const parsers = [
      makeParser({ parser_name: "nfyy", review_status: "stable" }),
      makeParser({ parser_name: "z2hospital", review_status: "watch" }),
    ];
    expect(shouldShowAllParserWarning(parsers)).toBe(false);
  });
});

describe("formatGeneratedAt", () => {
  it("formats ISO timestamp to YYYY-MM-DD HH:MM", () => {
    const result = formatGeneratedAt("2026-08-23T14:05:00");
    expect(result).toBe("2026-08-23 14:05");
  });

  it("pads single-digit month/day/hour/minute", () => {
    const result = formatGeneratedAt("2026-01-05T09:03:00");
    expect(result).toBe("2026-01-05 09:03");
  });
});
