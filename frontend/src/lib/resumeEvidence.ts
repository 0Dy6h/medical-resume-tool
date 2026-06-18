export function evidenceStrengthLabel(value?: string | null) {
  if (value === "strong") return "强匹配";
  if (value === "partial") return "部分匹配";
  if (value === "weak") return "弱匹配";
  return "待判断";
}

export function evidenceStrengthTone(value?: string | null): "success" | "working" | "idle" {
  if (value === "strong") return "success";
  if (value === "partial") return "working";
  return "idle";
}

export function evidenceSourceLabel(item: Record<string, unknown>) {
  const label = item.source_label;
  if (typeof label === "string" && label.trim()) return label;
  const fieldId = item.profile_field_id;
  return typeof fieldId === "string" && fieldId.trim() ? fieldId : "履历事实";
}
