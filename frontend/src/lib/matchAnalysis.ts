import type { MatchState } from "../types";

export function findingTone(status: MatchState): "success" | "working" | "danger" {
  if (status === "met") return "success";
  if (status === "partial") return "working";
  return "danger";
}

export function findingLabel(status: MatchState): string {
  if (status === "met") return "已满足";
  if (status === "partial") return "部分满足";
  if (status === "blocking") return "阻塞性差距";
  return "不满足";
}
