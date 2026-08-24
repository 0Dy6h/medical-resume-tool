import {
  Activity,
  BarChart3,
  BriefcaseBusiness,
  DatabaseZap,
  FileText,
  LayoutDashboard,
  LogOut,
  UserRound
} from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { useAuth } from "./components/AuthContext";
import { AnalyticsPage } from "./pages/AnalyticsPage";
import { CrawlPage } from "./pages/CrawlPage";
import { JobsPage } from "./pages/JobsPage";
import { LoginPage } from "./pages/LoginPage";
import { Overview } from "./pages/Overview";
import { ProfilePage } from "./pages/ProfilePage";
import { ResumePage } from "./pages/ResumePage";

type PageId = "overview" | "jobs" | "analytics" | "profile" | "resume" | "crawl";

const pages = [
  { id: "overview", label: "总览", icon: LayoutDashboard, group: "intelligence" },
  { id: "jobs", label: "岗位库", icon: BriefcaseBusiness, group: "intelligence" },
  { id: "analytics", label: "分析", icon: BarChart3, group: "intelligence" },
  { id: "profile", label: "我的履历", icon: UserRound, group: "mine" },
  { id: "resume", label: "简历生成", icon: FileText, group: "mine" },
  { id: "crawl", label: "抓取任务", icon: DatabaseZap, group: "mine" }
] satisfies Array<{ id: PageId; label: string; icon: typeof LayoutDashboard; group: "intelligence" | "mine" }>;

const GROUP_LABELS: Record<"intelligence" | "mine", string> = {
  intelligence: "情报",
  mine: "我的",
};

export default function App() {
  const auth = useAuth();
  const [active, setActive] = useState<PageId>("overview");
  const activePage = useMemo(() => pages.find((page) => page.id === active) ?? pages[0], [active]);
  const contentAreaRef = useRef<HTMLDivElement>(null);
  const topbarRef = useRef<HTMLElement>(null);
  const rafRef = useRef<number | null>(null);

  // C4: Topbar shadow on scroll — uses requestAnimationFrame throttling
  useEffect(() => {
    const contentArea = contentAreaRef.current;
    const topbar = topbarRef.current;
    if (!contentArea || !topbar) return;

    function handleScroll() {
      if (rafRef.current !== null) return;
      rafRef.current = requestAnimationFrame(() => {
        rafRef.current = null;
        const el = contentAreaRef.current;
        const tb = topbarRef.current;
        if (!el || !tb) return;
        if (el.scrollTop > 4) {
          tb.classList.add("scrolled");
        } else {
          tb.classList.remove("scrolled");
        }
      });
    }

    contentArea.addEventListener("scroll", handleScroll, { passive: true });
    return () => {
      contentArea.removeEventListener("scroll", handleScroll);
      if (rafRef.current !== null) {
        cancelAnimationFrame(rafRef.current);
      }
    };
  }, []);

  if (!auth.token) {
    return <LoginPage />;
  }

  // Group pages by their nav group
  const intelligencePages = pages.filter((p) => p.group === "intelligence");
  const minePages = pages.filter((p) => p.group === "mine");

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
          <div className="nav-group">
            <span className="nav-group-label">{GROUP_LABELS.intelligence}</span>
            {intelligencePages.map((page) => {
              const Icon = page.icon;
              return (
                <button className={active === page.id ? "nav-item active" : "nav-item"} key={page.id} onClick={() => setActive(page.id)}>
                  <Icon size={18} />
                  <span>{page.label}</span>
                </button>
              );
            })}
          </div>
          <div className="nav-group">
            <span className="nav-group-label">{GROUP_LABELS.mine}</span>
            {minePages.map((page) => {
              const Icon = page.icon;
              return (
                <button className={active === page.id ? "nav-item active" : "nav-item"} key={page.id} onClick={() => setActive(page.id)}>
                  <Icon size={18} />
                  <span>{page.label}</span>
                </button>
              );
            })}
          </div>
        </nav>
        <div className="sidebar-footer">
          <div className="sidebar-user">
            <UserRound size={16} />
            <span>{auth.username}</span>
          </div>
          <button className="nav-item logout" onClick={auth.logout}>
            <LogOut size={18} />
            <span>退出登录</span>
          </button>
        </div>
      </aside>
      <main className="main-workspace">
        <header className="topbar" ref={topbarRef}>
          <div>
            <span className="eyebrow">本地 MVP</span>
            <h2>{activePage.label}</h2>
          </div>
          <div className="topbar-badge">公开官网样本 · 真实履历重组</div>
        </header>
        <div className="content-area" ref={contentAreaRef}>
          {/* B1: Page transition — key changes on every page switch to re-trigger the animation */}
          <div key={active} className="page-enter">
            {active === "overview" && <Overview onNavigate={(page) => setActive(page as PageId)} />}
            {active === "jobs" && <JobsPage onNavigate={(page) => setActive(page as PageId)} />}
            {active === "analytics" && <AnalyticsPage onNavigate={(page) => setActive(page as PageId)} />}
            {active === "profile" && <ProfilePage />}
            {active === "resume" && <ResumePage />}
            {active === "crawl" && <CrawlPage />}
          </div>
        </div>
      </main>
    </div>
  );
}
