const labels: Record<string, string> = {
  never: "未抓取",
  success: "成功",
  failed: "失败",
  running: "运行中",
  completed: "完成",
  partial: "部分完成",
  completed_with_errors: "部分完成",
  review: "需复核",
  watch: "需关注",
  stable: "稳定",
  saved: "已收藏",
  evaluating: "评估中",
  preparing: "准备中",
  applied: "已投递",
  archived: "已归档"
};

export function statusLabel(value?: string | null): string {
  const status = value ?? "never";
  return labels[status] ?? status;
}

export function statusTone(value?: string | null): "danger" | "success" | "working" | "idle" {
  const status = value ?? "never";
  if (status.includes("fail")) return "danger";
  if (status === "review") return "danger";
  if (status === "partial" || status === "completed_with_errors") return "working";
  if (status === "watch") return "working";
  if (status === "evaluating" || status === "preparing") return "working";
  if (status === "saved") return "idle";
  if (status === "applied") return "success";
  if (status === "archived") return "idle";
  if (status === "stable") return "success";
  if (status.includes("success") || status.includes("completed")) return "success";
  if (status === "running") return "working";
  return "idle";
}
