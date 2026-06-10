import { ExternalLink, RefreshCcw, Search } from "lucide-react";
import { useEffect, useState } from "react";
import { api } from "../lib/api";
import { formatDate } from "../lib/format";
import type { Job, JobDetail } from "../types";

export function JobsPage() {
  const PAGE_SIZE = 50;
  const [keyword, setKeyword] = useState("");
  const [category, setCategory] = useState("");
  const [jobs, setJobs] = useState<Job[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(0);
  const [detail, setDetail] = useState<JobDetail | null>(null);
  const [loading, setLoading] = useState(false);

  async function refresh(targetPage = page) {
    setLoading(true);
    try {
      const payload = await api.jobs({
        keyword,
        job_category: category,
        limit: PAGE_SIZE,
        offset: targetPage * PAGE_SIZE,
      });
      setJobs(payload.items);
      setTotal(payload.total);
      setPage(targetPage);
      if (payload.items.length && !detail) {
        setDetail(await api.job(payload.items[0].id));
      }
    } finally {
      setLoading(false);
    }
  }

  function search() {
    void refresh(0);
  }

  async function selectJob(job: Job) {
    setDetail(await api.job(job.id));
  }

  useEffect(() => {
    void refresh(0);
  }, []);

  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  return (
    <div className="split-page">
      <section className="panel table-panel">
        <div className="toolbar compact">
          <div>
            <h1>岗位库</h1>
            <p className="subtle">{total} 条样本</p>
          </div>
          <button className="icon-button" onClick={() => void refresh()} disabled={loading} title="刷新">
            <RefreshCcw size={18} />
          </button>
        </div>
        <div className="filter-row">
          <label className="search-box">
            <Search size={17} />
            <input value={keyword} onChange={(event) => setKeyword(event.target.value)} onKeyDown={(event) => event.key === "Enter" && search()} placeholder="岗位、机构、能力" />
          </label>
          <select value={category} onChange={(event) => setCategory(event.target.value)}>
            <option value="">全部大类</option>
            {["临床", "护理", "医技", "药学", "科研", "教学", "公卫", "行政运营"].map((item) => (
              <option key={item} value={item}>{item}</option>
            ))}
          </select>
          <button className="icon-text-button" onClick={search}>
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
        {totalPages > 1 && (
          <div className="pagination-row">
            <button
              className="icon-text-button"
              onClick={() => void refresh(page - 1)}
              disabled={loading || page <= 0}
            >
              上一页
            </button>
            <span className="subtle">
              第 {page + 1} / {totalPages} 页
            </span>
            <button
              className="icon-text-button"
              onClick={() => void refresh(page + 1)}
              disabled={loading || page >= totalPages - 1}
            >
              下一页
            </button>
          </div>
        )}
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
            <h3>来源证据</h3>
            <div className="source-evidence">
              <EvidenceRow label="来源 URL" value={detail.source_url} link />
              <EvidenceRow label="文本哈希" value={detail.source_text_hash} />
              <EvidenceRow label="抓取时间" value={formatDate(detail.fetched_at)} />
              <EvidenceRow label="解析器" value={detail.parser_name} />
              <EvidenceRow label="置信度" value={`${Math.round(detail.confidence * 100)}%`} />
              {detail.extraction_evidence.announcement_url && (
                <EvidenceRow label="公告 URL" value={String(detail.extraction_evidence.announcement_url)} link />
              )}
              {detail.extraction_evidence.attachment_url && (
                <>
                  <EvidenceRow label="附件" value={String(detail.extraction_evidence.attachment_name ?? detail.extraction_evidence.attachment_url)} />
                  <EvidenceRow label="附件 URL" value={String(detail.extraction_evidence.attachment_url)} link />
                  <EvidenceRow label="表格位置" value={`${detail.extraction_evidence.sheet_name ?? "工作表"} / 第 ${detail.extraction_evidence.row_index ?? "-"} 行`} />
                </>
              )}
              {detail.extraction_evidence.attachments && detail.extraction_evidence.attachments.length > 0 && (
                <div className="attachment-list">
                  {detail.extraction_evidence.attachments.map((attachment, index) => (
                    <div className="attachment-item" key={`${String(attachment.url)}-${index}`}>
                      <strong>{String(attachment.name ?? "附件")}</strong>
                      <span>{String(attachment.status ?? "discovered")}</span>
                      {Boolean(attachment.url) && (
                        <a href={String(attachment.url)} target="_blank" rel="noreferrer">
                          {String(attachment.url)}
                        </a>
                      )}
                      {Boolean(attachment.error) && <p>{String(attachment.error)}</p>}
                    </div>
                  ))}
                </div>
              )}
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

function EvidenceRow({ label, value, link = false }: { label: string; value?: string | null; link?: boolean }) {
  if (!value) return null;
  return (
    <div className="evidence-row">
      <span>{label}</span>
      {link ? (
        <a href={value} target="_blank" rel="noreferrer">
          {value}
        </a>
      ) : (
        <strong>{value}</strong>
      )}
    </div>
  );
}
