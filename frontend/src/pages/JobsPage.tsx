import { ExternalLink, RefreshCcw, Search } from "lucide-react";
import { useEffect, useState } from "react";
import { api } from "../lib/api";
import { formatDate } from "../lib/format";
import type { Job, JobDetail } from "../types";

export function JobsPage() {
  const [keyword, setKeyword] = useState("");
  const [category, setCategory] = useState("");
  const [jobs, setJobs] = useState<Job[]>([]);
  const [total, setTotal] = useState(0);
  const [detail, setDetail] = useState<JobDetail | null>(null);
  const [loading, setLoading] = useState(false);

  async function refresh() {
    setLoading(true);
    try {
      const payload = await api.jobs({ keyword, job_category: category });
      setJobs(payload.items);
      setTotal(payload.total);
      if (payload.items.length && !detail) {
        setDetail(await api.job(payload.items[0].id));
      }
    } finally {
      setLoading(false);
    }
  }

  async function selectJob(job: Job) {
    setDetail(await api.job(job.id));
  }

  useEffect(() => {
    void refresh();
  }, []);

  return (
    <div className="split-page">
      <section className="panel table-panel">
        <div className="toolbar compact">
          <div>
            <h1>岗位库</h1>
            <p className="subtle">{total} 条样本</p>
          </div>
          <button className="icon-button" onClick={refresh} disabled={loading} title="刷新">
            <RefreshCcw size={18} />
          </button>
        </div>
        <div className="filter-row">
          <label className="search-box">
            <Search size={17} />
            <input value={keyword} onChange={(event) => setKeyword(event.target.value)} onKeyDown={(event) => event.key === "Enter" && void refresh()} placeholder="岗位、机构、能力" />
          </label>
          <select value={category} onChange={(event) => setCategory(event.target.value)}>
            <option value="">全部大类</option>
            {["临床", "护理", "医技", "药学", "科研", "教学", "公卫", "行政运营"].map((item) => (
              <option key={item} value={item}>{item}</option>
            ))}
          </select>
          <button className="icon-text-button" onClick={refresh}>
            <Search size={17} />
            查询
          </button>
        </div>
        <table>
          <thead>
            <tr>
              <th>岗位</th>
              <th>机构</th>
              <th>类别</th>
              <th>学历</th>
              <th>标签</th>
            </tr>
          </thead>
          <tbody>
            {jobs.map((job) => (
              <tr key={job.id} className={detail?.id === job.id ? "active-row" : ""} onClick={() => void selectJob(job)}>
                <td><strong>{job.title}</strong></td>
                <td>{job.institution_name}</td>
                <td>{job.job_category}</td>
                <td>{job.education}</td>
                <td>
                  <div className="tag-row">
                    {job.tags.slice(0, 4).map((tag) => <span className="tag" key={tag}>{tag}</span>)}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      <aside className="detail-panel">
        {detail ? (
          <>
            <div className="detail-head">
              <div>
                <h2>{detail.title}</h2>
                <span>{detail.institution_name}</span>
              </div>
              <a className="icon-button" href={detail.source_url} target="_blank" rel="noreferrer" title="来源">
                <ExternalLink size={18} />
              </a>
            </div>
            <div className="fact-grid">
              <span>部门</span><strong>{detail.department ?? "未注明"}</strong>
              <span>地区</span><strong>{detail.region}</strong>
              <span>学历</span><strong>{detail.education}</strong>
              <span>解析器</span><strong>{detail.parser_name}</strong>
              <span>置信度</span><strong>{Math.round(detail.confidence * 100)}%</strong>
              <span>抓取时间</span><strong>{formatDate(detail.fetched_at)}</strong>
            </div>
            <h3>职责</h3>
            <p>{detail.responsibilities}</p>
            <h3>要求</h3>
            <p>{detail.requirements}</p>
            <h3>标签</h3>
            <div className="tag-row">
              {detail.tags.map((tag) => <span className="tag" key={tag}>{tag}</span>)}
            </div>
            <h3>原文快照</h3>
            <pre>{detail.raw_snapshot.raw_text}</pre>
          </>
        ) : (
          <div className="empty-line">暂无选中岗位</div>
        )}
      </aside>
    </div>
  );
}
