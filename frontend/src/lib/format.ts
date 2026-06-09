export function formatDate(value?: string | null) {
  if (!value) return "未记录";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString("zh-CN", { hour12: false });
}

export function maxCount(items: Array<{ count: number }>) {
  return Math.max(1, ...items.map((item) => item.count));
}

