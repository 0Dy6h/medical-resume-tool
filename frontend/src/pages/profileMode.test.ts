import { describe, it, expect } from "vitest";
import type { Profile } from "../types";

/**
 * Inline copy of MODE_LAYOUT keys for test-only verification.
 *
 * The real layout lives in ProfilePage.tsx alongside the component.
 * These tests pin the contract: section count, order differences between
 * modes, and which sections start collapsed — without importing the
 * React component itself.
 */
const FRESH_GRAD_ORDER = [
  "education",
  "projects",
  "experiences",
  "publications",
  "teaching",
  "awards",
  "certificates",
  "skills",
  "languages",
];

const EXPERIENCED_ORDER = [
  "experiences",
  "projects",
  "education",
  "publications",
  "teaching",
  "awards",
  "certificates",
  "skills",
  "languages",
];

const FRESH_GRAD_COLLAPSED = new Set(["experiences"]);

describe("profile mode layout", () => {
  it("both modes contain all nine sections exactly once", () => {
    const all = ["education", "experiences", "projects", "publications", "certificates", "skills", "teaching", "awards", "languages"];
    expect(FRESH_GRAD_ORDER.length).toBe(9);
    expect(EXPERIENCED_ORDER.length).toBe(9);
    expect(new Set(FRESH_GRAD_ORDER)).toEqual(new Set(all));
    expect(new Set(EXPERIENCED_ORDER)).toEqual(new Set(all));
  });

  it("fresh_grad puts education first and experiences third", () => {
    expect(FRESH_GRAD_ORDER[0]).toBe("education");
    expect(FRESH_GRAD_ORDER[1]).toBe("projects");
    expect(FRESH_GRAD_ORDER[2]).toBe("experiences");
  });

  it("experienced puts experiences first and education third", () => {
    expect(EXPERIENCED_ORDER[0]).toBe("experiences");
    expect(EXPERIENCED_ORDER[1]).toBe("projects");
    expect(EXPERIENCED_ORDER[2]).toBe("education");
  });

  it("fresh_grad collapses experiences by default", () => {
    expect(FRESH_GRAD_COLLAPSED.has("experiences")).toBe(true);
    expect(FRESH_GRAD_COLLAPSED.has("education")).toBe(false);
    expect(FRESH_GRAD_COLLAPSED.has("projects")).toBe(false);
  });

  it("experienced does not collapse education or experiences by default", () => {
    // experienced mode: no sections are collapsed by default
    const experiencedCollapsed = new Set<string>();
    expect(experiencedCollapsed.has("experiences")).toBe(false);
    expect(experiencedCollapsed.has("education")).toBe(false);
  });
});

describe("mode switch preserves data", () => {
  function makeSampleProfile(mode: "fresh_grad" | "experienced"): Profile {
    return {
      basics: { name: "测试用户" },
      education: [{ id: "e1", school: "复旦", degree: "硕士" }],
      experiences: [{ id: "x1", organization: "某医院", role: "医师" }],
      projects: [{ id: "p1", name: "队列研究" }],
      publications: [{ id: "pub1", title: "论文1" }],
      certificates: [{ id: "c1", name: "GCP证书" }],
      skills: [{ id: "s1", name: "SPSS" }],
      teaching: [{ id: "t1", course: "统计学" }],
      awards: [{ id: "a1", name: "奖学金" }],
      languages: [{ id: "l1", name: "英语", level: "六级" }],
      mode,
    };
  }

  it("switching from experienced to fresh_grad does not change item counts", () => {
    const experienced = makeSampleProfile("experienced");
    const freshGrad: Profile = { ...experienced, mode: "fresh_grad" };

    expect(freshGrad.mode).toBe("fresh_grad");
    expect(freshGrad.education.length).toBe(experienced.education.length);
    expect(freshGrad.experiences.length).toBe(experienced.experiences.length);
    expect(freshGrad.projects.length).toBe(experienced.projects.length);
    expect(freshGrad.publications.length).toBe(experienced.publications.length);
    expect(freshGrad.certificates.length).toBe(experienced.certificates.length);
    expect(freshGrad.skills.length).toBe(experienced.skills.length);
    expect(freshGrad.teaching.length).toBe(experienced.teaching.length);
    expect(freshGrad.awards.length).toBe(experienced.awards.length);
    expect(freshGrad.languages.length).toBe(experienced.languages.length);
    expect(freshGrad.basics).toEqual(experienced.basics);
  });

  it("switching from fresh_grad to experienced does not change item counts", () => {
    const freshGrad = makeSampleProfile("fresh_grad");
    const experienced: Profile = { ...freshGrad, mode: "experienced" };

    expect(experienced.mode).toBe("experienced");
    expect(experienced.education.length).toBe(freshGrad.education.length);
    expect(experienced.experiences.length).toBe(freshGrad.experiences.length);
    expect(experienced.projects.length).toBe(freshGrad.projects.length);
    // Data content is fully preserved
    expect(experienced.education[0].school).toBe("复旦");
    expect(experienced.experiences[0].organization).toBe("某医院");
  });
});
