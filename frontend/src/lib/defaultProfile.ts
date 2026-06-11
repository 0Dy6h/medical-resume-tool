import type { Profile } from "../types";

export const emptyProfile: Profile = {
  education: [],
  experiences: [],
  projects: [],
  publications: [],
  certificates: [],
  skills: [],
  teaching: [],
  awards: [],
  languages: []
};

export const demoProfile: Profile = {
  education: [
    {
      id: "edu-1",
      school: "复旦大学",
      degree: "硕士",
      major: "临床医学",
      start: "2021",
      end: "2024",
      highlights: ["循证医学训练", "临床研究设计"]
    }
  ],
  experiences: [
    {
      id: "exp-1",
      organization: "上海某三甲医院",
      role: "科研助理",
      start: "2023",
      end: "2024",
      highlights: ["参与伦理材料整理", "维护随访数据库", "协助统计分析"],
      skills: ["临床研究", "SPSS", "数据管理"]
    }
  ],
  projects: [
    {
      id: "proj-1",
      name: "慢病队列随访项目",
      role: "项目成员",
      highlights: ["完成 300 例随访记录核查", "输出阶段性数据质量报告"],
      skills: ["随访", "数据质控"]
    }
  ],
  publications: [],
  certificates: [{ id: "cert-1", name: "大学英语六级", issuer: "教育部考试中心", year: "2022" }],
  skills: [{ id: "skill-1", name: "SPSS" }, { id: "skill-2", name: "临床研究" }],
  teaching: [],
  awards: [],
  languages: [{ id: "lang-1", name: "英语", level: "CET-6" }]
};

