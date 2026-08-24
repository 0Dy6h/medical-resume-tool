import { FileText, RefreshCcw } from "lucide-react";
import { useEffect, useState } from "react";
import { AnimatedNumber } from "../components/AnimatedNumber";
import { ButtonSpinner } from "../components/ButtonSpinner";
import { DataBar } from "../components/DataBar";
import { StatusPill } from "../components/StatusPill";
import { useToast } from "../components/Toast";
import { api } from "../lib/api";
import type { AnalyticsSummary, ParserQuality, Report } from "../types";

type AnalyticsPageProps = {
  onNavigate?: (page: string) => void;
};

type TabId = "market" | "quality";

export function AnalyticsPage({ onNavigate }: AnalyticsPageProps) {
  const toast = useToast();
  const [summary, setSummary] = useState<AnalyticsSummary | null>(null);
  const [report, setReport] = useState<Report | null>(null);
  const [loading, setLoading] = useState(false);
  const [reporting, setReporting] = useState(false);
  const [activeTab, setActiveTab] = useState<TabId>("market");
  const parserQuality = summary?.parser_quality ?? [];
  const reviewParserCount = parserQuality.filter((item) => item.review_status === "review").length;
  const totalJobs = summary?.totals.jobs ?? 0;
  const showParserWarning = shouldShowAllParserWarning(parserQuality);

  async function refresh() {
    setLoading(true);
    try {
      setSummary(await api.analytics());
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "加载分析数据失败");
    } finally {
      setLoading(false);
    }
  }

  async function createReport() {
    setReporting(true);
    try {
      setReport(await api.createReport("医疗岗位样本分析"));
      toast.success("已生成分析报告");
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "生成报告失败");
    } finally {
      setReporting(false);
    }
  }

  useEffect(() => {
    void refresh();
  }, []);

  // B6: Skeleton for metric grid
  const metricSkeleton = (
    <div className="metric-grid stagger-children">
      <div className="metric" aria-hidden="true">
        <span>岗位样本</span>
        <strong><span className="skeleton skeleton-text" style={{ width: "50%" }} /></strong>
      </div>
      <div className="metric" aria-hidden="true">
        <span>机构数量</span>
        <strong><span className="skeleton skeleton-text" style={{ width: "40%" }} /></strong>
      </div>
      <div className="metric" aria-hidden="true">
        <span>解析器</span>
        <strong><span className="skeleton skeleton-text" style={{ width: "40%" }} /></strong>
      </div>
      <div className="metric accent" aria-hidden="true">
        <span>需复核解析器</span>
        <strong><span className="skeleton skeleton-text" style={{ width: "30%" }} /></strong>
      </div>
      <span className="sr-only">加载中…</span>
    </div>
  );

  // B6: Skeleton for quality table
  const qualityTableSkeleton = (
    <table className="quality-table">
      <thead>
        <tr>
          <th>解析器</th>
          <th>岗位</th>
          <th>附件行</th>
          <th>低置信</th>
          <th>附件失败</th>
          <th>平均置信</th>
          <th>状态</th>
        </tr>
      </thead>
      <tbody className="stagger-children">
        {Array.from({ length: 6 }, (_, i) => (
          <tr key={`q-skel-${i}`} aria-hidden="true">
            <td><div className="skeleton skeleton-text" style={{ width: "70%" }} /></td>
            <td className="numeric-cell"><div className="skeleton skeleton-text" style={{ width: "40%", marginLeft: "auto" }} /></td>
            <td className="numeric-cell"><div className="skeleton skeleton-text" style={{ width: "40%", marginLeft: "auto" }} /></td>
            <td className="numeric-cell"><div className="skeleton skeleton-text" style={{ width: "40%", marginLeft: "auto" }} /></td>
            <td className="numeric-cell"><div className="skeleton skeleton-text" style={{ width: "40%", marginLeft: "auto" }} /></td>
            <td className="numeric-cell"><div className="skeleton skeleton-text" style={{ width: "50%", marginLeft: "auto" }} /></td>
            <td><div className="skeleton skeleton-text" style={{ width: "60%" }} /></td>
          </tr>
        ))}
        <tr><td colSpan={7} className="sr-only">加载中…</td></tr>
      </tbody>
    </table>
  );

  return (
    <div className="page-stack">
      <div className="toolbar">
        <div>
          <h1>分析</h1>
          <p className="subtle">岗位方向、学历要求、共性能力、机构重点</p>
        </div>
        <div className="button-row">
          <div className="mode-switch" role="tablist" aria-label="分析视角">
            <button
              role="tab"
              aria-selected={activeTab === "market"}
              className={activeTab === "market" ? "mode-tab active" : "mode-tab"}
              onClick={() => setActiveTab("market")}
            >
              市场洞察
            </button>
            <button
              role="tab"
              aria-selected={activeTab === "quality"}
              className={activeTab === "quality" ? "mode-tab active" : "mode-tab"}
              onClick={() => setActiveTab("quality")}
            >
              数据质量
            </button>
          </div>
          <button className="secondary-button" onClick={refresh} disabled={loading}>
            <RefreshCcw size={17} />
            刷新
          </button>
          {/* Task C: 生成报告是本页主 CTA */}
          <button className="primary-button" onClick={createReport} disabled={reporting}>
            {reporting ? <ButtonSpinner /> : <FileText size={17} />}
            {reporting ? "生成中…" : "报告"}
          </button>
        </div>
      </div>

      {showParserWarning && (
        <div className="warning-banner">
          所有解析器均处于失效状态，相关机构职位推送已暂停，请等待修复
        </div>
      )}

      {totalJobs === 0 && !loading ? (
        <section className="empty-state">
          <p>暂无数据，请先执行一次爬取任务</p>
          {onNavigate && (
            <button className="primary-button" onClick={() => onNavigate("crawl")}>
              前往抓取任务
            </button>
          )}
        </section>
      ) : activeTab === "market" ? (
        <>
          {/* B5 + B6: Metric grid with animated numbers and skeleton */}
          {loading && !summary ? metricSkeleton : (
            <div className="metric-grid stagger-children">
              <div className="metric"><span>岗位样本</span><strong><AnimatedNumber value={summary?.totals.jobs ?? 0} /></strong></div>
              <div className="metric"><span>机构数量</span><strong><AnimatedNumber value={summary?.totals.institutions ?? 0} /></strong></div>
              <div className="metric"><span>解析器</span><strong><AnimatedNumber value={summary?.totals.parsers ?? 0} /></strong></div>
              <div className="metric accent"><span>需复核解析器</span><strong><AnimatedNumber value={reviewParserCount} /></strong></div>
            </div>
          )}

          <div className="analysis-grid">
            <DataBar title="岗位大类" items={summary?.job_categories ?? []} />
            <DataBar title="学历要求" items={summary?.education_levels ?? []} />
            <DataBar title="机构类型" items={summary?.institution_types ?? []} />
            <DataBar title="地区分布" items={summary?.regions ?? []} />
            <DataBar title="共性能力" items={summary?.common_capabilities ?? []} />
          </div>

          <section className="panel">
            <div className="panel-head">
              <h2>机构发力方向</h2>
            </div>
            <div className="compact-list stagger-children">
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
        </>
      ) : (
        <section className="panel table-panel">
          <div className="panel-head">
            <h2>解析器质量</h2>
            <span className="subtle">低置信 {summary?.totals.low_confidence_jobs ?? 0} · 附件失败 {summary?.totals.failed_attachment_events ?? 0}</span>
          </div>
          {loading && parserQuality.length === 0 ? qualityTableSkeleton : parserQuality.length === 0 ? (
            <div className="empty-line">暂无数据</div>
          ) : (
            <table className="quality-table">
              <thead>
                <tr>
                  <th>解析器</th>
                  <th>岗位</th>
                  <th>附件行</th>
                  <th>低置信</th>
                  <th>附件失败</th>
                  <th>平均置信</th>
                  <th>状态</th>
                </tr>
              </thead>
              {/* B4: Stagger enter for quality table rows */}
              <tbody className="stagger-children">
                {parserQuality.map((item) => (
                  <tr key={item.parser_name}>
                    <td className="parser-name"><strong>{item.parser_name}</strong></td>
                    <td className="numeric-cell">{item.jobs}</td>
                    <td className="numeric-cell">{item.attachment_sourced_jobs}</td>
                    <td className="numeric-cell">{item.low_confidence_jobs}</td>
                    <td className="numeric-cell">{item.failed_attachment_events}</td>
                    <td className="numeric-cell">{Math.round(item.average_confidence * 100)}%</td>
                    <td><StatusPill value={item.review_status} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </section>
      )}

      {report && (
        <section className="panel report-panel">
          <div className="panel-head">
            <h2>{report.title}</h2>
            <span className="subtle">#{report.id}</span>
          </div>
          <div
            className="report-content"
            dangerouslySetInnerHTML={{ __html: extractReportBody(report.html) }}
          />
        </section>
      )}

      {summary?.generated_at && (
        <div className="subtle" style={{ textAlign: "right", fontSize: "12px" }}>
          数据更新于：{formatGeneratedAt(summary.generated_at)}
        </div>
      )}
    </div>
  );
}

export function shouldShowAllParserWarning(parsers: ParserQuality[]): boolean {
  return parsers.length > 0 && parsers.every((p) => p.review_status === "review");
}

export function formatGeneratedAt(iso: string): string {
  const d = new Date(iso);
  const yyyy = d.getFullYear();
  const mm = String(d.getMonth() + 1).padStart(2, "0");
  const dd = String(d.getDate()).padStart(2, "0");
  const hh = String(d.getHours()).padStart(2, "0");
  const min = String(d.getMinutes()).padStart(2, "0");
  return `${yyyy}-${mm}-${dd} ${hh}:${min}`;
}

function extractReportBody(html: string): string {
  const match = html.match(/<body>([\s\S]*)<\/body>/i);
  return match ? match[1] : html;
}
