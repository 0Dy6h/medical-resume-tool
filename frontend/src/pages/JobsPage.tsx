import { BookmarkCheck, BookmarkPlus, ExternalLink, RefreshCcw, Search, WandSparkles, X } from "lucide-react";
import { useEffect, useState } from "react";
import { StatusPill } from "../components/StatusPill";
import { useToast } from "../components/Toast";
import { api } from "../lib/api";
import { formatDate } from "../lib/format";
import { findingLabel, findingTone } from "../lib/matchAnalysis";
import type { Job, JobDetail, JobMatch } from "../types";

const EDUCATION_LEVELS = ["博士", "硕士", "本科", "大专"];
const JOB_STATUS_OPTIONS = [
  { value: "saved", label: "收藏" },
  { value: "evaluating", label: "评估中" },
  { value: "preparing", label: "准备中" },
  { value: "applied", label: "已投递" },
  { value: "archived", label: "归档" }
];

export type MatchLabel =
  | { kind: "none" }
  | { kind: "blocking" }
  | { kind: "ok"; text: string; percent: number };

export function computeMatchLabel(match: JobMatch | null | undefined): MatchLabel {
  if (!match) return { kind: "none" };
  if (match.blocking_gap) return { kind: "blocking" };
  return {
    kind: "ok",
    text: `满足 ${match.met}/${match.total} 项硬性要求`,
    percent: match.degree_percent,
  };
}

export function freshnessTag(
  postedAt: string | null | undefined,
  fetchedAt: string | null | undefined,
  now: Date = new Date()
): "" | "新" | "今日" {
  const ts = postedAt ?? fetchedAt;
  if (!ts) return "";
  const postDate = new Date(ts);
  const ageMs = now.getTime() - postDate.getTime();
  if (ageMs < 0) return "";
  const ageHours = ageMs / (1000 * 60 * 60);
  if (ageHours <= 24) return "新";
  const postDay = new Date(postDate.getFullYear(), postDate.getMonth(), postDate.getDate());
  const nowDay = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const dayDiff = Math.round((nowDay.getTime() - postDay.getTime()) / (1000 * 60 * 60 * 24));
  if (dayDiff <= 1) return "今日";
  return "";
}

export function canGenerateDraft(matchAnalysis: unknown): boolean {
  return matchAnalysis != null;
}

export function JobsPage({ onNavigate }: { onNavigate: (page: string) => void }) {
  const PAGE_SIZE = 50;
  const toast = useToast();
  const [keyword, setKeyword] = useState("");
  const [category, setCategory] = useState("");
  const [region, setRegion] = useState("");
  const [institutionType, setInstitutionType] = useState("");
  const [education, setEducation] = useState("");
  const [regions, setRegions] = useState<string[]>([]);
  const [institutionTypes, setInstitutionTypes] = useState<string[]>([]);
  const [jobs, setJobs] = useState<Job[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(0);
  const [detail, setDetail] = useState<JobDetail | null>(null);
  const [loading, setLoading] = useState(false);
  const [statusValue, setStatusValue] = useState("saved");
  const [statusNote, setStatusNote] = useState("");
  const [statusDeadline, setStatusDeadline] = useState("");
  const [generatingDraft, setGeneratingDraft] = useState(false);

  async function refresh(targetPage = page) {
    setLoading(true);
    try {
      const payload = await api.jobs({
        keyword,
        job_category: category,
        region,
        institution_type: institutionType,
        education,
        limit: PAGE_SIZE,
        offset: targetPage * PAGE_SIZE,
      });
      setJobs(payload.items);
      setTotal(payload.total);
      setPage(targetPage);
      if (payload.items.length && !detail) {
        const firstDetail = await api.job(payload.items[0].id);
        setDetail(firstDetail);
        syncStatusForm(firstDetail);
      }
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "加载岗位失败");
    } finally {
      setLoading(false);
    }
  }

  function search() {
    void refresh(0);
  }

  async function selectJob(job: Job) {
    try {
      const payload = await api.job(job.id);
      setDetail(payload);
      syncStatusForm(payload);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "加载岗位详情失败");
    }
  }

  function syncStatusForm(job: JobDetail | null) {
    setStatusValue(job?.user_status?.status ?? "saved");
    setStatusNote(job?.user_status?.note ?? "");
    setStatusDeadline(job?.user_status?.deadline ?? "");
  }

  async function saveStatus() {
    if (!detail) return;
    try {
      const userStatus = await api.saveJobStatus(detail.id, {
        status: statusValue,
        note: statusNote.trim() || null,
        deadline: statusDeadline.trim() || null
      });
      setDetail({ ...detail, user_status: userStatus });
      setJobs((current) => current.map((job) => (job.id === detail.id ? { ...job, user_status: userStatus } : job)));
      toast.success("岗位状态已保存");
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "保存岗位状态失败");
    }
  }

  async function clearStatus() {
    if (!detail) return;
    try {
      await api.clearJobStatus(detail.id);
      setDetail({ ...detail, user_status: null });
      setJobs((current) => current.map((job) => (job.id === detail.id ? { ...job, user_status: null } : job)));
      syncStatusForm(null);
      toast.success("已清除岗位状态");
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "清除岗位状态失败");
    }
  }

  async function generateDraft() {
    if (!detail || detail.match_analysis == null) return;
    setGeneratingDraft(true);
    try {
      const draft = await api.createResumeDraft(detail.id);
      localStorage.setItem("pending_resume_draft_id", String(draft.id));
      onNavigate("resume");
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "生成简历草稿失败");
    } finally {
      setGeneratingDraft(false);
    }
  }

  useEffect(() => {
    void refresh(0);
    api
      .analytics()
      .then((summary) => {
        setRegions(summary.regions.map((item) => item.name));
        setInstitutionTypes(summary.institution_types.map((item) => item.name));
      })
      .catch(() => {
        /* 筛选项加载失败不阻断岗位列表 */
      });
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
          <select value={region} onChange={(event) => setRegion(event.target.value)}>
            <option value="">全部地区</option>
            {regions.map((item) => (
              <option key={item} value={item}>{item}</option>
            ))}
          </select>
          <select value={institutionType} onChange={(event) => setInstitutionType(event.target.value)}>
            <option value="">全部机构类型</option>
            {institutionTypes.map((item) => (
              <option key={item} value={item}>{item}</option>
            ))}
          </select>
          <select value={education} onChange={(event) => setEducation(event.target.value)}>
            <option value="">全部学历</option>
            {EDUCATION_LEVELS.map((item) => (
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
              <th>匹配度</th>
              <th>状态</th>
              <th>标签</th>
            </tr>
          </thead>
          <tbody>
            {jobs.length === 0 ? (
              <tr>
                <td colSpan={7} className="loading-line">
                  {loading ? "加载中…" : "未找到匹配岗位"}
                </td>
              </tr>
            ) : (
              jobs.map((job) => {
                const freshTag = freshnessTag(job.posted_at, job.fetched_at);
                const matchLabel = computeMatchLabel(job.match);
                return (
                <tr key={job.id} className={detail?.id === job.id ? "active-row" : ""} onClick={() => void selectJob(job)}>
                  <td>
                    <div className="job-title-cell">
                      {freshTag && <span className={`freshness-badge freshness-${freshTag}`}>{freshTag}</span>}
                      <strong>{job.title}</strong>
                    </div>
                  </td>
                  <td>{job.institution_name}</td>
                  <td>{job.job_category}</td>
                  <td>{job.education}</td>
                  <td>
                    {matchLabel.kind === "none" && (
                      <button className="match-guide-link" onClick={(e) => { e.stopPropagation(); onNavigate("profile"); }}>
                        请完善档案以查看匹配度
                      </button>
                    )}
                    {matchLabel.kind === "blocking" && (
                      <div className="match-cell">
                        <span className="match-badge blocking">硬性不符</span>
                        <div className="match-bar-track"><span className="match-bar-fill" style={{ width: "0%" }} /></div>
                      </div>
                    )}
                    {matchLabel.kind === "ok" && (
                      <div className="match-cell">
                        <div className="match-bar-track"><span className="match-bar-fill" style={{ width: `${matchLabel.percent}%` }} /></div>
                        <span className="match-text">{matchLabel.text}</span>
                      </div>
                    )}
                  </td>
                  <td>{job.user_status ? <StatusPill value={job.user_status.status} /> : <span className="subtle">未评估</span>}</td>
                  <td>
                    <div className="tag-row">
                      {job.tags.slice(0, 4).map((tag) => <span className="tag" key={tag}>{tag}</span>)}
                    </div>
                  </td>
                </tr>
                );
              })
            )}
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
            {detail.confidence < 0.6 && (
              <div className="match-warning-bar">
                该职位由系统自动解析，部分信息可能存在误差，建议点击原始链接核对
              </div>
            )}
            <div className="fact-grid">
              <span>部门</span><strong>{detail.department ?? "未注明"}</strong>
              <span>地区</span><strong>{detail.region}</strong>
              <span>学历</span><strong>{detail.education}</strong>
              <span>解析器</span><strong>{detail.parser_name}</strong>
              <span>置信度</span><strong>{Math.round(detail.confidence * 100)}%</strong>
              <span>抓取时间</span><strong>{formatDate(detail.fetched_at)}</strong>
            </div>
            <section className="job-action-panel">
              <div className="panel-head compact-head">
                <h3>投递决策</h3>
                {detail.user_status ? <StatusPill value={detail.user_status.status} /> : <span className="status idle">未评估</span>}
              </div>
              <div className="status-form">
                <label>
                  <span>状态</span>
                  <select value={statusValue} onChange={(event) => setStatusValue(event.target.value)}>
                    {JOB_STATUS_OPTIONS.map((option) => (
                      <option value={option.value} key={option.value}>{option.label}</option>
                    ))}
                  </select>
                </label>
                <label>
                  <span>截止/提醒</span>
                  <input value={statusDeadline} onChange={(event) => setStatusDeadline(event.target.value)} placeholder="如 2026-07-01" />
                </label>
                <label className="span-2">
                  <span>备注</span>
                  <textarea value={statusNote} onChange={(event) => setStatusNote(event.target.value)} placeholder="记录投递材料、联系人或复核点" />
                </label>
              </div>
              <div className="button-row">
                <button className="primary-button" onClick={() => void saveStatus()}>
                  {detail.user_status ? <BookmarkCheck size={17} /> : <BookmarkPlus size={17} />}
                  保存状态
                </button>
                <button className="icon-text-button" onClick={() => void clearStatus()} disabled={!detail.user_status}>
                  <X size={17} />
                  清除
                </button>
              </div>
            </section>
            <h3>职责</h3>
            <p>{detail.responsibilities}</p>
            <h3>要求</h3>
            <p>{detail.requirements}</p>
            <section className="match-analysis-panel">
              <div className="panel-head">
                <h3>硬性要求匹配分析</h3>
              </div>
              {detail.match_analysis == null ? (
                <div className="match-analysis-empty">
                  <span className="subtle">登录并完善档案后查看匹配分析</span>
                  <button className="match-guide-link" onClick={() => onNavigate("profile")}>去完善档案</button>
                </div>
              ) : (
                <>
                  {detail.match_analysis.map((finding, index) => (
                    <div className={`match-finding-card ${finding.status}`} key={`${finding.requirement}-${index}`}>
                      <div className="match-finding-bar" />
                      <div className="match-finding-body">
                        <div className="match-finding-head">
                          <strong>{finding.requirement}</strong>
                          <span className={`status ${findingTone(finding.status)}`}>{findingLabel(finding.status)}</span>
                        </div>
                        {finding.evidence.length > 0 && (
                          <div className="match-finding-evidence">
                            {finding.evidence.map((ev, i) => (
                              <div className="evidence-row" key={i}>
                                <span>{ev.source ?? "履历"}</span>
                                <strong>{ev.text ?? "—"}</strong>
                              </div>
                            ))}
                          </div>
                        )}
                        {finding.advice && <p className="match-finding-advice">{finding.advice}</p>}
                      </div>
                    </div>
                  ))}
                  <div className="draft-generate-row">
                    <button
                      className="primary-button draft-generate-button"
                      onClick={() => void generateDraft()}
                      disabled={generatingDraft}
                    >
                      <WandSparkles size={17} />
                      {generatingDraft ? "生成中…" : "生成简历草稿"}
                    </button>
                  </div>
                </>
              )}
            </section>
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
