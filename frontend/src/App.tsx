import {
  Activity,
  BarChart3,
  BriefcaseBusiness,
  DatabaseZap,
  FileText,
  LayoutDashboard,
  UserRound
} from "lucide-react";
import { useMemo, useState } from "react";
import { AnalyticsPage } from "./pages/AnalyticsPage";
import { CrawlPage } from "./pages/CrawlPage";
import { JobsPage } from "./pages/JobsPage";
import { Overview } from "./pages/Overview";
import { ProfilePage } from "./pages/ProfilePage";
import { ResumePage } from "./pages/ResumePage";

type PageId = "overview" | "jobs" | "analytics" | "profile" | "resume" | "crawl";

const pages = [
  { id: "overview", label: "总览", icon: LayoutDashboard },
  { id: "jobs", label: "岗位库", icon: BriefcaseBusiness },
  { id: "analytics", label: "分析", icon: BarChart3 },
  { id: "profile", label: "我的履历", icon: UserRound },
  { id: "resume", label: "简历生成", icon: FileText },
  { id: "crawl", label: "抓取任务", icon: DatabaseZap }
] satisfies Array<{ id: PageId; label: string; icon: typeof LayoutDashboard }>;

export default function App() {
  const [active, setActive] = useState<PageId>("overview");
  const activePage = useMemo(() => pages.find((page) => page.id === active) ?? pages[0], [active]);

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-mark"><Activity size={22} /></div>
          <div>
            <strong>医疗岗位情报</strong>
            <span>Resume Lab</span>
          </div>
        </div>
        <nav>
          {pages.map((page) => {
            const Icon = page.icon;
            return (
              <button className={active === page.id ? "nav-item active" : "nav-item"} key={page.id} onClick={() => setActive(page.id)}>
                <Icon size={18} />
                <span>{page.label}</span>
              </button>
            );
          })}
        </nav>
      </aside>
      <main className="main-workspace">
        <header className="topbar">
          <div>
            <span className="eyebrow">本地 MVP</span>
            <h2>{activePage.label}</h2>
          </div>
          <div className="topbar-badge">公开官网样本 · 真实履历重组</div>
        </header>
        <div className="content-area">
          {active === "overview" && <Overview onNavigate={(page) => setActive(page as PageId)} />}
          {active === "jobs" && <JobsPage />}
          {active === "analytics" && <AnalyticsPage />}
          {active === "profile" && <ProfilePage />}
          {active === "resume" && <ResumePage />}
          {active === "crawl" && <CrawlPage />}
        </div>
      </main>
    </div>
  );
}

