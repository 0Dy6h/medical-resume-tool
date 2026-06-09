import { FileText, RefreshCcw } from "lucide-react";
import { useEffect, useState } from "react";
import { DataBar } from "../components/DataBar";
import { api } from "../lib/api";
import type { AnalyticsSummary, Report } from "../types";

export function AnalyticsPage() {
  const [summary, setSummary] = useState<AnalyticsSummary | null>(null);
  const [report, setReport] = useState<Report | null>(null);
  const [loading, setLoading] = useState(false);

  async function refresh() {
    setLoading(true);
    try {
      setSummary(await api.analytics());
    } finally {
      setLoading(false);
    }
  }

  async function createReport() {
    setReport(await api.createReport("医疗岗位样本分析"));
  }

  useEffect(() => {
    void refresh();
  }, []);

  return (
    <div className="page-stack">
      <div className="toolbar">
        <div>
          <h1>分析</h1>
          <p className="subtle">岗位方向、学历要求、共性能力、机构重点</p>
        </div>
        <div className="button-row">
          <button className="icon-text-button" onClick={refresh} disabled={loading}>
            <RefreshCcw size={17} />
            刷新
          </button>
          <button className="primary-button" onClick={createReport}>
            <FileText size={17} />
            报告
          </button>
        </div>
      </div>

      <div className="metric-grid">
        <div className="metric"><span>岗位样本</span><strong>{summary?.totals.jobs ?? 0}</strong></div>
        <div className="metric"><span>机构数量</span><strong>{summary?.totals.institutions ?? 0}</strong></div>
        <div className="metric"><span>覆盖地区</span><strong>{summary?.totals.regions ?? 0}</strong></div>
        <div className="metric accent"><span>最高频能力</span><strong>{summary?.common_capabilities[0]?.name ?? "暂无"}</strong></div>
      </div>

      <div className="analysis-grid">
        <DataBar title="岗位大类" items={summary?.job_categories ?? []} />
        <DataBar title="学历要求" items={summary?.education_levels ?? []} />
        <DataBar title="机构类型" items={summary?.institution_types ?? []} />
        <DataBar title="共性能力" items={summary?.common_capabilities ?? []} />
      </div>

      <section className="panel">
        <div className="panel-head">
          <h2>机构发力方向</h2>
        </div>
        <div className="compact-list">
          {(summary?.institution_focus ?? []).slice(0, 12).map((item) => (
            <div className="compact-row" key={item.institution}>
              <strong>{item.institution}</strong>
              <div className="tag-row">
                {item.focus.map((focus) => <span className="tag" key={focus.name}>{focus.name} {focus.count}</span>)}
              </div>
            </div>
          ))}
        </div>
      </section>

      {report && (
        <section className="panel report-panel">
          <div className="panel-head">
            <h2>{report.title}</h2>
            <span className="subtle">#{report.id}</span>
          </div>
          <pre>{report.markdown}</pre>
        </section>
      )}
    </div>
  );
}

