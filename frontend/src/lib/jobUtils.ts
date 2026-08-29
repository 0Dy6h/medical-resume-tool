export function foldTags(
  tags: string[],
  maxVisible = 2,
): { visible: string[]; hidden: string[]; remaining: number } {
  const visible = tags.slice(0, maxVisible);
  const hidden = tags.slice(maxVisible);
  return { visible, hidden, remaining: hidden.length };
}

export type DataTrust = "real" | "placeholder" | "fixture" | "disabled";

export const TRUST_LABELS: Record<DataTrust, string> = {
  real: "真实",
  placeholder: "待复核",
  fixture: "演示",
  disabled: "历史",
};

/** 非真实数据在列表/详情中必须降级标记，不得冒充真实岗位。 */
export function trustBadge(trust: DataTrust | undefined): { label: string; tone: string } | null {
  if (!trust || trust === "real") return null;
  if (trust === "placeholder") return { label: "占位·待复核", tone: "placeholder" };
  if (trust === "fixture") return { label: "演示数据", tone: "fixture" };
  return { label: "机构已禁用·历史", tone: "disabled" };
}
