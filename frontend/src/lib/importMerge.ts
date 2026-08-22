import type { Profile, ProfileImportResult } from "../types";

type Item = Record<string, unknown>;

export type MergeResult = {
  profile: Profile;
  /** Number of entries actually written into the profile. */
  accepted: number;
};

/**
 * Merge the entries a user ticked in the import preview into their profile.
 *
 * Kept pure and separate from the page so the accumulation order is testable:
 * a collection can receive both auto-extracted items and review items in the
 * same confirm, and every accepted entry has to survive.
 */
export function mergeImportSelection(
  profile: Profile,
  preview: ProfileImportResult,
  selectedKeys: ReadonlySet<string>,
  collections: readonly (keyof Profile)[],
  makeId: (prefix: string) => string,
  selectedBasics?: Record<string, string>
): MergeResult {
  const next: Profile = { ...profile };
  let accepted = 0;

  for (const collection of collections) {
    const items = (preview[collection as keyof ProfileImportResult] as Item[] | undefined) ?? [];
    const picked = items
      .filter((_, index) => selectedKeys.has(`${String(collection)}-${index}`))
      .map((item) => ({ ...item, id: makeId(String(collection)) }));
    if (picked.length === 0) continue;
    accepted += picked.length;
    next[collection] = [...((next[collection] as Item[] | undefined) ?? []), ...picked] as never;
  }

  (preview.review_items ?? []).forEach((reviewItem, index) => {
    if (!selectedKeys.has(`review-${index}`)) return;
    const collection = reviewItem.collection as keyof Profile;
    if (!collections.includes(collection)) return;
    const item = { ...(reviewItem.item as Item), id: makeId(String(collection)) };
    accepted += 1;
    next[collection] = [...((next[collection] as Item[] | undefined) ?? []), item] as never;
  });

  if (selectedBasics && Object.keys(selectedBasics).length > 0) {
    next.basics = { ...(next.basics ?? {}), ...selectedBasics };
    accepted += Object.keys(selectedBasics).length;
  }

  return { profile: next, accepted };
}
