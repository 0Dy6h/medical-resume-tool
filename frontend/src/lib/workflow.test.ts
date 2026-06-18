import { describe, expect, it } from "vitest";
import { emptyProfile } from "./defaultProfile";
import { onboardingPaths, profileFactCount, workflowSteps } from "./workflow";
import type { AnalyticsSummary } from "../types";

const summary = (jobs: number): AnalyticsSummary => ({
  totals: {
    jobs,
    institutions: jobs ? 6 : 0,
    regions: jobs ? 3 : 0,
    parsers: jobs ? 1 : 0,
    low_confidence_jobs: 0,
    attachment_sourced_jobs: 0,
    failed_attachment_events: 0
  },
  job_categories: [],
  education_levels: [],
  institution_types: [],
  regions: [],
  common_capabilities: [],
  institution_focus: [],
  parser_quality: []
});

describe("workflow helpers", () => {
  it("counts structured profile facts across all sections", () => {
    expect(profileFactCount({ ...emptyProfile, skills: [{ id: "s1" }], education: [{ id: "e1" }] })).toBe(2);
  });

  it("guides empty users to crawl before resume generation", () => {
    const steps = workflowSteps(summary(0), emptyProfile);
    expect(steps[0].done).toBe(false);
    expect(steps[0].target).toBe("crawl");
    expect(steps[2].target).toBe("crawl");
  });

  it("unlocks resume generation after jobs and facts exist", () => {
    const steps = workflowSteps(summary(12), { ...emptyProfile, skills: [{ id: "s1" }] });
    expect(steps.every((step) => step.done)).toBe(true);
    expect(steps[2].target).toBe("resume");
  });

  it("offers separate stable demo and private workflow entries", () => {
    const emptyPaths = onboardingPaths(summary(0), emptyProfile);
    expect(emptyPaths.map((path) => path.id)).toEqual(["demo", "private"]);
    expect(emptyPaths[0].target).toBe("crawl");
    expect(emptyPaths[0].action).toContain("fixture");
    expect(emptyPaths[1].target).toBe("profile");

    const readyPaths = onboardingPaths(summary(12), { ...emptyProfile, skills: [{ id: "s1" }] });
    expect(readyPaths[0].target).toBe("jobs");
    expect(readyPaths[1].target).toBe("resume");
  });
});
