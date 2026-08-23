import { CheckSquare, Loader2, Play, RefreshCcw, Square } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { StatusPill } from "../components/StatusPill";
import { useToast } from "../components/Toast";
import { api } from "../lib/api";
import { formatDate, isDemoStrategy } from "../lib/format";
import type { CrawlRun, Institution } from "../types";

const TERMINAL_STATUSES = new Set(["completed", "partial", "failed"]);

/**
 * Compute adaptation coverage from an institution list.
 *
 * Pure function — safe to test directly. Returns the count of enabled
 * (adapted) institutions and the total count of all institutions.
 */
export function adaptationCoverage(institutions: Institution[]): { adapted: number; total: number } {
  const adapted = institutions.filter((item) => item.enabled).length;
  return { adapted, total: institutions.length };
}

/**
 * Compute the set of all adapted (enabled) institution IDs.
 *
 * Pure function — used by "全选" to exclude non-adapted institutions.
 */
export function allAdaptedIds(institutions: Institution[]): Set<number> {
  return new Set(institutions.filter((item) => item.enabled).map((item) => item.id));
}

export function CrawlPage() {
  const toast = useToast();
  const [institutions, setInstitutions] = useState<Institution[]>([]);
  const [selected, setSelected] = useState<Set<number>>(new Set([1, 2, 3, 4, 5, 6]));
  const [run, setRun] = useState<CrawlRun | null>(null);
  const [loading, setLoading] = useState(false);
  const pollRef = useRef<number | null>(null);

  async function refresh() {
    try {
      setInstitutions(await api.institutions());
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "加载机构失败");
    }
  }

  useEffect(() => {
    void refresh();
    return () => {
      if (pollRef.current) window.clearInterval(pollRef.current);
    };
  }, []);

  const selectedIds = useMemo(() => Array.from(selected).sort((a, b) => a - b), [selected]);
  const crawling = loading || (run !== null && !TERMINAL_STATUSES.has(run.status));
  const coverage = useMemo(() => adaptationCoverage(institutions), [institutions]);

  function poll(runId: number) {
    if (pollRef.current) window.clearInterval(pollRef.current);
    pollRef.current = window.setInterval(async () => {
      try {
        const payload = await api.crawlRun(runId);
        setRun(payload);
        if (TERMINAL_STATUSES.has(payload.status)) {
          if (pollRef.current) window.clearInterval(pollRef.current);
          pollRef.current = null;
          await refresh();
          if (payload.status === "completed") {
            toast.success(`抓取完成：成功 ${payload.success_count} 条`);
          } else if (payload.status === "partial") {
            toast.info(`部分完成：成功 ${payload.success_count}，失败 ${payload.failure_count}`);
          } else {
            toast.error(`抓取失败：${payload.failure_count} 个机构未成功`);
          }
        }
      } catch (error) {
        if (pollRef.current) window.clearInterval(pollRef.current);
        pollRef.current = null;
        toast.error(error instanceof Error ? error.message : "轮询抓取进度失败");
      }
    }, 1500);
  }

  async function startCrawl() {
    setLoading(true);
    try {
      const payload = await api.startCrawl(selectedIds);
      setRun(payload);
      toast.info(`已启动抓取 ${selectedIds.length} 家机构`);
      poll(payload.id);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "启动抓取失败");
    } finally {
      setLoading(false);
    }
  }

  function toggle(id: number) {
    setSelected((current) => {
      const next = new Set(current);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  function selectAll() {
    setSelected(allAdaptedIds(institutions));
  }

  function selectNone() {
    setSelected(new Set());
  }

  function selectEnabled() {
    setSelected(allAdaptedIds(institutions));
  }

  const allAdaptedSelected = useMemo(() => {
    const adapted = institutions.filter((item) => item.enabled);
    if (adapted.length === 0) return false;
    return adapted.every((item) => selected.has(item.id));
  }, [institutions, selected]);

  return (
    <div className="page-stack">
      <div className="toolbar">
        <div>
          <h1>抓取任务</h1>
          <p className="subtle">机构种子、公开页面、抓取状态（策略为 fixture 的是内置演示数据，非真实抓取）</p>
        </div>
        <div className="button-row">
          <button className="icon-text-button" onClick={refresh} disabled={crawling}>
            <RefreshCcw size={17} />
            刷新
          </button>
          <button className="primary-button" onClick={startCrawl} disabled={crawling || selectedIds.length === 0}>
            {crawling ? <Loader2 size={17} className="spin" /> : <Play size={17} />}
            {crawling ? "抓取中…" : "启动"}
          </button>
        </div>
      </div>

      {run && (
        <section className="panel run-panel run-panel-detail">
          <div className="run-summary">
            <StatusPill value={run.status} />
            <span>任务 #{run.id}</span>
            <span>成功 {run.success_count}</span>
            <span>失败 {run.failure_count}</span>
            {crawling ? (
              <span className="progress-track">
                <span className="progress-fill" style={{ width: "100%", opacity: 0.5 }} />
              </span>
            ) : (
              <span>{formatDate(run.completed_at)}</span>
            )}
          </div>
          {(run.errors ?? run.error_summary).length > 0 && (
            <div className="error-strip">
              {(run.errors ?? run.error_summary).map((error, index) => (
                <div className="error-item" key={`${String(error.institution_id)}-${index}`}>
                  <strong>{String(error.institution ?? error.institution_id ?? "未知机构")}</strong>
                  <span>{String(error.error ?? "抓取失败")}</span>
                </div>
              ))}
            </div>
          )}
        </section>
      )}

      <section className="panel table-panel">
        <div className="panel-head">
          <div>
            <h2>机构种子</h2>
            <p className="subtle">机构覆盖：{coverage.adapted}/{coverage.total} 已适配</p>
          </div>
          <div className="button-row">
            <button className="text-button" onClick={selectEnabled}>仅已启用</button>
            <button className="text-button" onClick={selectAll}>全选</button>
            <button className="text-button" onClick={selectNone}>全不选</button>
            <span className="subtle">{selectedIds.length} 家已选择</span>
          </div>
        </div>
        <table>
          <thead>
            <tr>
              <th>
                <button className="icon-button small" onClick={allAdaptedSelected ? selectNone : selectAll} title="全选/全不选（仅已适配机构）">
                  {allAdaptedSelected ? <CheckSquare size={17} /> : <Square size={17} />}
                </button>
              </th>
              <th>机构</th>
              <th>类型</th>
              <th>地区</th>
              <th>策略</th>
              <th>状态</th>
              <th>最近抓取</th>
            </tr>
          </thead>
          <tbody>
            {institutions.map((item) => {
              const isDisabled = !item.enabled;
              return (
                <tr key={item.id}>
                  <td>
                    <button
                      className="icon-button small"
                      onClick={() => !isDisabled && toggle(item.id)}
                      disabled={isDisabled}
                      title={isDisabled ? item.blocked_reason ?? "尚未适配该站点，暂未启用" : "选择"}
                    >
                      {selected.has(item.id) ? <CheckSquare size={17} /> : <Square size={17} />}
                    </button>
                  </td>
                  <td>
                    <a href={item.official_url} target="_blank" rel="noreferrer">
                      {item.name}
                    </a>
                  </td>
                  <td>{item.institution_type}</td>
                  <td>{item.region}</td>
                  <td>
                    <div className="status-cell">
                      <span>{item.crawl_strategy}</span>
                      {isDemoStrategy(item.crawl_strategy) && <span className="tag">演示数据</span>}
                      {isDisabled && <span className="tag">未适配</span>}
                    </div>
                  </td>
                  <td>
                    <div className="status-cell">
                      {isDisabled ? (
                        <span className="status-error">
                          {item.blocked_reason ?? "尚未适配该站点，暂未启用"}
                        </span>
                      ) : (
                        <>
                          <StatusPill value={item.last_status} />
                          {item.last_error && <span className="status-error">{item.last_error}</span>}
                        </>
                      )}
                    </div>
                  </td>
                  <td>{formatDate(item.last_crawled_at)}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </section>
    </div>
  );
}
