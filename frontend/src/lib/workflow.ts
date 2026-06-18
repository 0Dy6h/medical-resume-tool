import type { AnalyticsSummary, Profile } from "../types";

const PROFILE_COLLECTIONS: Array<keyof Profile> = [
  "education",
  "experiences",
  "projects",
  "publications",
  "certificates",
  "skills",
  "teaching",
  "awards",
  "languages"
];

export function profileFactCount(profile?: Profile | null) {
  if (!profile) return 0;
  return PROFILE_COLLECTIONS.reduce((total, key) => total + ((profile[key] as unknown[])?.length ?? 0), 0);
}

export function workflowSteps(summary?: AnalyticsSummary | null, profile?: Profile | null) {
  const jobs = summary?.totals.jobs ?? 0;
  const facts = profileFactCount(profile);
  return [
    {
      id: "jobs",
      title: "岗位样本",
      done: jobs > 0,
      action: jobs > 0 ? "查看岗位库" : "加载演示数据",
      target: jobs > 0 ? "jobs" : "crawl",
      detail: jobs > 0 ? `${jobs} 条岗位可用于匹配` : "先用前 6 家 fixture 机构跑通稳定演示"
    },
    {
      id: "profile",
      title: "履历事实",
      done: facts > 0,
      action: facts > 0 ? "检查履历" : "导入或使用示例",
      target: "profile",
      detail: facts > 0 ? `${facts} 条结构化事实` : "简历草稿只会使用这里已有的事实"
    },
    {
      id: "resume",
      title: "证据化草稿",
      done: jobs > 0 && facts > 0,
      action: jobs > 0 && facts > 0 ? "生成草稿" : "补齐前置步骤",
      target: jobs > 0 && facts > 0 ? "resume" : jobs > 0 ? "profile" : "crawl",
      detail: "按岗位要求匹配证据，同时列出缺口"
    }
  ];
}

export function onboardingPaths(summary?: AnalyticsSummary | null, profile?: Profile | null) {
  const jobs = summary?.totals.jobs ?? 0;
  const facts = profileFactCount(profile);
  return [
    {
      id: "demo",
      title: "稳定演示入口",
      detail: jobs > 0 ? `${jobs} 条岗位样本已就绪，先挑一个目标岗位。` : "用前 6 家 fixture 机构加载确定性样本，先跑通演示链路。",
      action: jobs > 0 ? "查看岗位" : "加载 fixture 样本",
      target: jobs > 0 ? "jobs" : "crawl"
    },
    {
      id: "private",
      title: "私密履历入口",
      detail: facts > 0 ? `${facts} 条本地履历事实已保存，可生成证据化草稿。` : "导入或填写本地履历事实，草稿不会编造缺失经历。",
      action: jobs > 0 && facts > 0 ? "生成草稿" : "整理履历",
      target: jobs > 0 && facts > 0 ? "resume" : "profile"
    }
  ];
}
