type StatusPillProps = {
  value?: string | null;
};

export function StatusPill({ value }: StatusPillProps) {
  const status = value ?? "never";
  const tone = status.includes("fail")
    ? "danger"
    : status.includes("success") || status.includes("completed")
      ? "success"
      : status === "running"
        ? "working"
        : "idle";
  const label: Record<string, string> = {
    never: "未抓取",
    success: "成功",
    failed: "失败",
    running: "运行中",
    completed: "完成",
    completed_with_errors: "部分完成"
  };
  return <span className={`status ${tone}`}>{label[status] ?? status}</span>;
}

