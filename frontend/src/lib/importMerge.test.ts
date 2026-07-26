import { describe, expect, it } from "vitest";
import { mergeImportSelection } from "./importMerge";
import { emptyProfile } from "./defaultProfile";
import type { Profile, ProfileImportResult } from "../types";

const collections = [
  "education",
  "experiences",
  "projects",
  "publications",
  "certificates",
  "skills",
  "teaching",
  "awards",
  "languages"
] as const satisfies readonly (keyof Profile)[];

let counter = 0;
const makeId = (prefix: string) => `${prefix}-${++counter}`;

function selection(...keys: string[]) {
  return new Set(keys);
}

describe("mergeImportSelection", () => {
  it("appends the ticked auto-extracted items", () => {
    counter = 0;
    const preview = {
      skills: [{ name: "SPSS" }, { name: "R" }]
    } as unknown as ProfileImportResult;

    const { profile, accepted } = mergeImportSelection(
      emptyProfile,
      preview,
      selection("skills-0", "skills-1"),
      collections,
      makeId
    );

    expect(accepted).toBe(2);
    expect((profile.skills as Array<{ name: string }>).map((s) => s.name)).toEqual(["SPSS", "R"]);
  });

  it("skips items the user unticked", () => {
    counter = 0;
    const preview = {
      skills: [{ name: "SPSS" }, { name: "R" }]
    } as unknown as ProfileImportResult;

    const { profile, accepted } = mergeImportSelection(
      emptyProfile,
      preview,
      selection("skills-1"),
      collections,
      makeId
    );

    expect(accepted).toBe(1);
    expect((profile.skills as Array<{ name: string }>).map((s) => s.name)).toEqual(["R"]);
  });

  it("keeps every review item accepted for the same collection", () => {
    // Regression: the loop read the pre-merge profile, so all but the last
    // review item per collection was silently dropped while the toast still
    // reported the full count.
    counter = 0;
    const preview = {
      skills: [],
      review_items: [
        { collection: "skills", item: { name: "队列研究" }, source_text: "", confidence: 0.4, warnings: [] },
        { collection: "skills", item: { name: "随访管理" }, source_text: "", confidence: 0.4, warnings: [] },
        { collection: "skills", item: { name: "课题申报" }, source_text: "", confidence: 0.4, warnings: [] }
      ]
    } as unknown as ProfileImportResult;

    const { profile, accepted } = mergeImportSelection(
      emptyProfile,
      preview,
      selection("review-0", "review-1", "review-2"),
      collections,
      makeId
    );

    expect(accepted).toBe(3);
    expect((profile.skills as Array<{ name: string }>).map((s) => s.name)).toEqual([
      "队列研究",
      "随访管理",
      "课题申报"
    ]);
  });

  it("keeps auto-extracted and review items for the same collection together", () => {
    counter = 0;
    const preview = {
      skills: [{ name: "SPSS" }],
      review_items: [
        { collection: "skills", item: { name: "队列研究" }, source_text: "", confidence: 0.4, warnings: [] }
      ]
    } as unknown as ProfileImportResult;

    const { profile, accepted } = mergeImportSelection(
      emptyProfile,
      preview,
      selection("skills-0", "review-0"),
      collections,
      makeId
    );

    expect(accepted).toBe(2);
    expect((profile.skills as Array<{ name: string }>).map((s) => s.name)).toEqual(["SPSS", "队列研究"]);
  });

  it("preserves entries the profile already had", () => {
    counter = 0;
    const existing = { ...emptyProfile, skills: [{ id: "s0", name: "已有技能" }] } as Profile;
    const preview = { skills: [{ name: "SPSS" }] } as unknown as ProfileImportResult;

    const { profile } = mergeImportSelection(existing, preview, selection("skills-0"), collections, makeId);

    expect((profile.skills as Array<{ name: string }>).map((s) => s.name)).toEqual(["已有技能", "SPSS"]);
  });

  it("does not mutate the profile it was given", () => {
    counter = 0;
    const existing = { ...emptyProfile, skills: [{ id: "s0", name: "已有技能" }] } as Profile;
    const preview = { skills: [{ name: "SPSS" }] } as unknown as ProfileImportResult;

    mergeImportSelection(existing, preview, selection("skills-0"), collections, makeId);

    expect((existing.skills as unknown[]).length).toBe(1);
  });

  it("ignores a review item naming an unknown collection", () => {
    counter = 0;
    const preview = {
      review_items: [
        { collection: "hobbies", item: { name: "跑步" }, source_text: "", confidence: 0.2, warnings: [] }
      ]
    } as unknown as ProfileImportResult;

    const { accepted } = mergeImportSelection(emptyProfile, preview, selection("review-0"), collections, makeId);

    expect(accepted).toBe(0);
  });

  it("gives every accepted item a distinct id", () => {
    counter = 0;
    const preview = {
      skills: [{ name: "SPSS" }, { name: "R" }],
      review_items: [
        { collection: "skills", item: { name: "队列研究" }, source_text: "", confidence: 0.4, warnings: [] }
      ]
    } as unknown as ProfileImportResult;

    const { profile } = mergeImportSelection(
      emptyProfile,
      preview,
      selection("skills-0", "skills-1", "review-0"),
      collections,
      makeId
    );

    const ids = (profile.skills as Array<{ id: string }>).map((s) => s.id);
    expect(new Set(ids).size).toBe(3);
  });
});
