import { Activity, ArrowRight, BriefcaseBusiness, Building2, CheckCircle2, DatabaseZap, FileText, MapPinned, RefreshCcw, ShieldCheck, UserRound } from "lucide-react";
import { useEffect, useState } from "react";
import { useToast } from "../components/Toast";
import { api } from "../lib/api";
import { formatDate } from "../lib/format";
import { onboardingPaths, workflowSteps } from "../lib/workflow";
import type { AnalyticsSummary, Job, Profile } from "../types";

type OverviewProps = {
  onNavigate: (page: string) => void;
};

export function Overview({ onNavigate }: OverviewProps) {
  const toast = useToast();
  const [summary, setSummary] = useState<AnalyticsSummary | null>(null);
  const [jobs, setJobs] = useState<Job[]>([]);
  const [profile, setProfile] = useState<Profile | null>(null);
  const [loading, setLoading] = useState(false);

  async function refresh() {
    setLoading(true);
    try {
      const [summaryPayload, jobsPayload, profilePayload] = await Promise.all([api.analytics(), api.jobs(), api.profile()]);
      setSummary(summaryPayload);
      setJobs(jobsPayload.items.slice(0, 6));
      setProfile(profilePayload);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "加载总览数据失败");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void refresh();
  }, []);

  const steps = workflowSteps(summary, profile);
  const paths = onboardingPaths(summary, profile);
  const readyForResume = steps.every((step) => step.done);

  return (
    <div className="page-stack">
      <div className="toolbar">
        <div>
          <h1>总览</h1>
          <p className="subtle">公开官网岗位样本与本地履历状态</p>
        </div>
        <button className="icon-button" onClick={refresh} disabled={loading} title="刷新">
          <RefreshCcw size={18} />
        </button>
      </div>

      <div className="metric-grid">
        <button className="metric" onClick={() => onNavigate("jobs")}>
          <BriefcaseBusiness size={20} />
          <span>岗位</span>
          <strong>{summary?.totals.jobs ?? 0}</strong>
        </button>
        <button className="metric" onClick={() => onNavigate("crawl")}>
          <Building2 size={20} />
          <span>机构</span>
          <strong>{summary?.totals.institutions ?? 0}</strong>
        </button>
        <button className="metric" onClick={() => onNavigate("analytics")}>
          <MapPinned size={20} />
          <span>地区</span>
          <strong>{summary?.totals.regions ?? 0}</strong>
        </button>
        <button className="metric accent" onClick={() => onNavigate("resume")}>
          <Activity size={20} />
          <span>高频能力</span>
          <strong>{summary?.common_capabilities[0]?.name ?? "待抓取"}</strong>
        </button>
      </div>

      <section className="panel launch-panel">
        <div className="launch-copy">
          <span className="eyebrow">下一步</span>
          <h2>{readyForResume ? "证据链已就绪，可以生成投递版简历" : "先跑通岗位样本和履历事实，再生成草稿"}</h2>
          <p className="subtle">目标是形成一条可复查链路：官网岗位要求、你的真实履历证据、可导出的投递版简历。</p>
        </div>
        <div className="onboarding-paths">
          {paths.map((path) => (
            <button className="onboarding-path" key={path.id} onClick={() => onNavigate(path.target)}>
              <span className="path-icon">
                {path.id === "demo" ? <DatabaseZap size={18} /> : <ShieldCheck size={18} />}
              </span>
              <span>
                <strong>{path.title}</strong>
                <em>{path.detail}</em>
              </span>
              <b>{path.action}</b>
            </button>
          ))}
        </div>
        <div className="workflow-grid">
          {steps.map((step, index) => (
            <button className={step.done ? "workflow-card done" : "workflow-card"} key={step.id} onClick={() => onNavigate(step.target)}>
              <div className="workflow-icon">
                {step.id === "jobs" && <DatabaseZap size={18} />}
                {step.id === "profile" && <UserRound size={18} />}
                {step.id === "resume" && <FileText size={18} />}
              </div>
              <div>
                <span>0{index + 1}</span>
                <strong>{step.title}</strong>
                <p>{step.detail}</p>
              </div>
              {step.done ? <CheckCircle2 size={18} /> : <ArrowRight size={18} />}
              <em>{step.action}</em>
            </button>
          ))}
        </div>
      </section>

      <section className="panel">
        <div className="panel-head">
          <h2>近期岗位</h2>
          <button className="text-button" onClick={() => onNavigate("jobs")}>查看岗位库</button>
        </div>
        <div className="compact-list">
          {jobs.length === 0 ? (
            <div className="empty-line">暂无岗位样本</div>
          ) : (
            jobs.map((job) => (
              <div className="compact-row" key={job.id}>
                <div>
                  <strong>{job.title}</strong>
                  <span>{job.institution_name}</span>
                </div>
                <div className="row-meta">
                  <span>{job.job_category}</span>
                  <span>{formatDate(job.fetched_at)}</span>
                </div>
              </div>
            ))
          )}
        </div>
      </section>
    </div>
  );
}
