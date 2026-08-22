/**
 * Pure functions for profile boundary-check UI logic (PRD 4.3).
 *
 * These functions encapsulate the decision logic and copy text for the two
 * confirmation dialogs on the profile page:
 *
 * 1. **Delete guard** — when a profile item is referenced by ≥1 resume draft,
 *    show a warning before deleting.
 * 2. **Overlap guard** — when saving a profile whose education/experiences
 *    contain time-overlapping entries, ask for confirmation before saving.
 *
 * The functions are pure (no side effects, no React, no fetch) so they can
 * be unit-tested in isolation without rendering components.
 */

export type FieldReferenceResult = {
  field_id: string;
  count: number;
  draft_ids: number[];
};

export type OverlapCheckResult = {
  overlap: boolean;
  items: Array<Record<string, unknown>>;
};

/**
 * True when at least one resume draft references the field — the delete
 * guard should fire.
 */
export function shouldShowDeleteWarning(result: FieldReferenceResult): boolean {
  return result.count > 0;
}

/**
 * Warning copy shown in the delete confirmation dialog.
 *
 * "该记录已被用于生成 X 份简历草稿，删除后相关草稿的证据链将断裂"
 */
export function formatDeleteWarning(count: number): string {
  return `该记录已被用于生成 ${count} 份简历草稿，删除后相关草稿的证据链将断裂`;
}

/**
 * True when the overlap check found any time-overlapping entries — the
 * save guard should fire.
 */
export function shouldShowOverlapWarning(result: OverlapCheckResult): boolean {
  return result.overlap;
}

/**
 * Warning copy shown in the overlap confirmation dialog.
 *
 * "检测到可能与已有记录重叠的经历，是否继续添加？"
 */
export function formatOverlapWarning(): string {
  return "检测到可能与已有记录重叠的经历，是否继续添加？";
}
