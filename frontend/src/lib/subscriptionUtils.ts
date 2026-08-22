import type { Subscription } from "../types";

/**
 * Format the "last pushed" timestamp for subscription cards.
 * - Within 1 minute: "刚刚"
 * - Within 1 hour: "X 分钟前"
 * - Within 24 hours: "X 小时前"
 * - Older: date string from formatDate
 */
export function formatLastPushed(
  lastCheckedAt: string | null | undefined,
  now: Date = new Date()
): string {
  if (!lastCheckedAt) return "未检查";
  const date = new Date(lastCheckedAt);
  if (Number.isNaN(date.getTime())) return lastCheckedAt;
  const diffMs = now.getTime() - date.getTime();
  if (diffMs < 0) return "刚刚";
  const diffMinutes = Math.floor(diffMs / (1000 * 60));
  if (diffMinutes < 1) return "刚刚";
  if (diffMinutes < 60) return `${diffMinutes} 分钟前`;
  const diffHours = Math.floor(diffMinutes / 60);
  if (diffHours < 24) return `${diffHours} 小时前`;
  return date.toLocaleDateString("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false
  });
}

/**
 * Validate subscription form fields.
 * Returns an error message, or empty string if valid.
 */
export function validateSubscriptionForm(payload: {
  name: string;
  keyword: string;
  institutionIds: number[];
}): string {
  const name = payload.name.trim();
  if (name.length < 2) return "订阅名称至少 2 个字符";
  if (name.length > 30) return "订阅名称不能超过 30 个字符";

  const keyword = payload.keyword.trim();
  if (keyword.length < 1) return "请输入关键词";
  if (keyword.length > 50) return "关键词不能超过 50 个字符";

  if (payload.institutionIds.length < 1) return "请至少选择 1 家机构";
  if (payload.institutionIds.length > 12) return "最多选择 12 家机构";

  return "";
}

/**
 * Get the display subtitle for a subscription card.
 * Shows "N 条新职位 · 上次推送时间" or the 30-day empty message.
 */
export function subscriptionSubtitle(sub: Subscription): string {
  if (sub.is_empty_30d && sub.new_count === 0) {
    return "近 30 天无新职位";
  }
  return `${sub.new_count} 条新职位 · 上次推送 ${formatLastPushed(sub.last_checked_at)}`;
}

/**
 * Count how many institutions are in maintenance mode.
 */
export function countMaintenanceInstitutions(
  statuses: Array<{ is_maintenance: boolean }>
): number {
  return statuses.filter((s) => s.is_maintenance).length;
}

/**
 * Broad keyword threshold: warn if match ratio exceeds this value.
 * Mirrors backend BROAD_KEYWORD_RATIO = 0.5
 * This is a client-side hint only; the server is the source of truth.
 */
export const BROAD_KEYWORD_THRESHOLD = 0.5;

/**
 * Check if a warning string indicates a broad keyword.
 * Pure helper for conditionally displaying warning UI.
 */
export function hasBroadKeywordWarning(warning: string | null | undefined): boolean {
  return Boolean(warning && warning.includes("关键词过宽"));
}
