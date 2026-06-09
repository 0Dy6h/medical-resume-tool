import { Activity, BriefcaseBusiness, Building2, MapPinned, RefreshCcw } from "lucide-react";
import { useEffect, useState } from "react";
import { api } from "../lib/api";
import { formatDate } from "../lib/format";
import type { AnalyticsSummary, Job } from "../types";

type OverviewProps = {
  onNavigate: (page: string) => void;
};

export function Overview({ onNavigate }: OverviewProps) {
  const [summary, setSummary] = useState<AnalyticsSummary | null>(null);
  const [jobs, setJobs] = useState<Job[]>([]);
  const [loading, setLoading] = useState(false);

  async function refresh() {
    setLoading(true);
    try {
      const [summaryPayload, jobsPayload] = await Promise.all([api.analytics(), api.jobs()]);
      setSummary(summaryPayload);
      setJobs(jobsPayload.items.slice(0, 6));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void refresh();
  }, []);

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

