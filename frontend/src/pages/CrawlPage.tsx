import { CheckSquare, Play, RefreshCcw, Square } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { StatusPill } from "../components/StatusPill";
import { api } from "../lib/api";
import { formatDate } from "../lib/format";
import type { CrawlRun, Institution } from "../types";

export function CrawlPage() {
  const [institutions, setInstitutions] = useState<Institution[]>([]);
  const [selected, setSelected] = useState<Set<number>>(new Set([1, 2, 3, 4, 5, 6]));
  const [run, setRun] = useState<CrawlRun | null>(null);
  const [loading, setLoading] = useState(false);

  async function refresh() {
    const payload = await api.institutions();
    setInstitutions(payload);
  }

  useEffect(() => {
    void refresh();
  }, []);

  const selectedIds = useMemo(() => Array.from(selected).sort((a, b) => a - b), [selected]);

  async function startCrawl() {
    setLoading(true);
    try {
      const payload = await api.startCrawl(selectedIds);
      setRun(payload);
      await refresh();
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

  return (
    <div className="page-stack">
      <div className="toolbar">
        <div>
          <h1>抓取任务</h1>
          <p className="subtle">机构种子、公开页面、抓取状态</p>
        </div>
        <div className="button-row">
          <button className="icon-text-button" onClick={refresh}>
            <RefreshCcw size={17} />
            刷新
          </button>
          <button className="primary-button" onClick={startCrawl} disabled={loading || selectedIds.length === 0}>
            <Play size={17} />
            启动
          </button>
        </div>
      </div>

      {run && (
        <section className="panel run-panel">
          <StatusPill value={run.status} />
          <span>任务 #{run.id}</span>
          <span>成功 {run.success_count}</span>
          <span>失败 {run.failure_count}</span>
          <span>{formatDate(run.completed_at)}</span>
        </section>
      )}

      <section className="panel table-panel">
        <div className="panel-head">
          <h2>机构种子</h2>
          <span className="subtle">{selectedIds.length} 家已选择</span>
        </div>
        <table>
          <thead>
            <tr>
              <th>选择</th>
              <th>机构</th>
              <th>类型</th>
              <th>地区</th>
              <th>策略</th>
              <th>状态</th>
              <th>最近抓取</th>
            </tr>
          </thead>
          <tbody>
            {institutions.map((item) => (
              <tr key={item.id}>
                <td>
                  <button className="icon-button small" onClick={() => toggle(item.id)} title="选择">
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
                <td>{item.crawl_strategy}</td>
                <td><StatusPill value={item.last_status} /></td>
                <td>{formatDate(item.last_crawled_at)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    </div>
  );
}

