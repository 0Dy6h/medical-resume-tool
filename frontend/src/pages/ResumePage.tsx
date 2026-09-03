import { CheckCircle2, ChevronLeft, ChevronRight, Download, FileDown, History, ListChecks, Pencil, RefreshCcw, Save, Trash2, WandSparkles } from "lucide-react";
import { useEffect, useState } from "react";
import { ButtonSpinner } from "../components/ButtonSpinner";
import { useToast } from "../components/Toast";
import { api, downloadBlob } from "../lib/api";
import { evidenceSourceLabel, evidenceStrengthLabel, evidenceStrengthTone } from "../lib/resumeEvidence";
import type { Job, ResumeDraft, ResumeDraftSummary, ResumeSection } from "../types";

// ── Pure helpers (exported for testing) ──────────────────────────────

export type ReviewEntry = {
  sectionId: string;
  sectionTitle: string;
  itemIndex: number;
  text: string;
  profile_field_id?: string;
  evidence_level?: string;
  decision?: "adopt" | "edit" | "remove";
};

export function flattenReviewItems(sections: ResumeSection[]): ReviewEntry[] {
  const entries: ReviewEntry[] = [];
  for (const section of sections) {
    for (let i = 0; i < section.items.length; i++) {
      const item = section.items[i];
      entries.push({
        sectionId: section.id,
        sectionTitle: section.title,
        itemIndex: i,
        text: item.text,
        profile_field_id: item.profile_field_id,
        evidence_level: item.evidence_level,
        decision: item.decision,
      });
    }
  }
  return entries;
}

export function computeDraftStatus(sections: ResumeSection[]): "draft" | "reviewed" {
  const items = sections.flatMap((s) => s.items);
  if (items.length === 0) return "draft";
  return items.every((item) => item.decision === "adopt" || item.decision === "edit" || item.decision === "remove")
    ? "reviewed"
    : "draft";
}

export function reviewTone(
  item: { profile_field_id?: string; evidence_level?: string; text?: string },
  evidence: Array<Record<string, unknown>>,
): "green" | "yellow" | "red" {
  const fieldId = item.profile_field_id;
  if (fieldId) {
    const ev = evidence.find((e) => e.profile_field_id === fieldId);
    if (ev) {
      const strength = String(ev.evidence_strength ?? "");
      if (strength === "strong") return "green";
      if (strength === "partial" || strength === "weak") return "yellow";
    }
  }
  if (item.evidence_level === "matched") return "green";
  if (item.evidence_level === "supporting") return "yellow";
  return "red";
}

export function filterExportSections(sections: ResumeSection[]): ResumeSection[] {
  return sections.map((section) => ({
    ...section,
    items: section.items.filter((item) => item.decision !== "remove"),
  }));
}

export type ExportGuardResult =
  | { kind: "proceed" }
  | { kind: "confirm"; pending: number };

export function exportBlock(sections: ResumeSection[]): ExportGuardResult {
  if (computeDraftStatus(sections) === "reviewed") return { kind: "proceed" };
  const items = sections.flatMap((s) => s.items);
  const pending = items.filter(
    (item) => item.decision !== "adopt" && item.decision !== "edit" && item.decision !== "remove",
  ).length;
  return { kind: "confirm", pending };
}

export type ReviewCompletion =
  | { kind: "complete" }
  | { kind: "blocked"; pending: number; firstPendingIndex: number };

/**
 * B3：完成审阅的门禁 —— 存在未决策条目时禁止完成，
 * 并定位到第一个待确认条目。旧版「自动补 adopt」行为已废除。
 */
export function reviewCompletion(sections: ResumeSection[]): ReviewCompletion {
  let pending = 0;
  let firstPendingIndex = -1;
  flattenReviewItems(sections).forEach((item, index) => {
    if (item.decision !== "adopt" && item.decision !== "edit" && item.decision !== "remove") {
      pending += 1;
      if (firstPendingIndex < 0) firstPendingIndex = index;
    }
  });
  return pending === 0
    ? { kind: "complete" }
    : { kind: "blocked", pending, firstPendingIndex };
}

/**
 * B3：投递版导出前统计将随导出、但未绑定档案证据的条目数
 * （身份 / 求职意向 / 缺口提醒区块不计入，已删除条目不计入）。
 */
export function unlinkedExportCount(sections: ResumeSection[]): number {
  return flattenReviewItems(sections).filter(
    (item) => item.decision !== "remove" && isUnlinkedReviewItem(item, item.sectionId),
  ).length;
}

const UNLINKED_SKIP_SECTION_IDS = new Set([
  "identity",
  "target",
  "gaps",
  "appendix",
  "appendix-satisfied",
  "appendix-unmet",
  "appendix-unlinked",
]);
const UNLINKED_SKIP_SECTION_TITLE = "投递前需补充确认";

export function isUnlinkedReviewItem(
  item: { text?: string; profile_field_id?: string; decision?: string; sectionTitle?: string },
  sectionId: string,
): boolean {
  if (UNLINKED_SKIP_SECTION_IDS.has(sectionId)) return false;
  if (item.sectionTitle?.trim() === UNLINKED_SKIP_SECTION_TITLE) return false;
  if (item.decision === "remove") return false;
  return !String(item.profile_field_id ?? "").trim();
}

export const PENDING_DRAFT_KEY = "pending_resume_draft_id";

export function readPendingDraftId(storage: { getItem: (key: string) => string | null }): number | null {
  const raw = storage.getItem(PENDING_DRAFT_KEY);
  if (raw == null) return null;
  const id = Number(raw);
  return Number.isFinite(id) && id > 0 ? id : null;
}

/**
 * 切换目标岗位时，当前显示的草稿若属于其他岗位，必须清除，
 * 禁止“选择器已切到岗位 B，页面仍显示/导出岗位 A 的草稿”。
 */
export function shouldResetDraftOnJobChange(
  nextJobId: number | "",
  draft: { job_id: number } | null,
): boolean {
  if (draft == null) return false;
  if (nextJobId === "") return false;
  return draft.job_id !== nextJobId;
}

/**
 * P0-2：学历等硬性门槛被 422 阻断时，toast 几秒即逝、页面停留在空态死胡同。
 * 识别阻断类错误文案，转为页面内常驻提示 + 「去岗位库」出口；
 * 非阻断错误（网络等）返回 null，维持 toast 行为。
 */
export function mismatchNoticeFromError(message: string): string | null {
  return message.includes("差距较大") ? message : null;
}

// ── Review card colours (matching PRD 4.4 prototype) ────────────────

const TONE_STYLES: Record<"green" | "yellow" | "red", { bg: string; border: string; color: string; label: string }> = {
  green: { bg: "#f0fdf4", border: "#bbf7d0", color: "#166534", label: "已满足" },
  yellow: { bg: "#fffbeb", border: "#fde68a", color: "#92400e", label: "部分满足" },
  red: { bg: "#fef2f2", border: "#fecaca", color: "#991b1b", label: "待确认" },
};

const DECISION_LABEL: Record<string, string> = {
  adopt: "已采纳",
  edit: "已修改",
  remove: "已删除",
};

// ── Component ────────────────────────────────────────────────────────

export function ResumePage({ onNavigate }: { onNavigate?: (page: string) => void }) {
  const toast = useToast();
  const [jobs, setJobs] = useState<Job[]>([]);
  const [jobId, setJobId] = useState<number | "">("");
  const [draft, setDraft] = useState<ResumeDraft | null>(null);
  const [loading, setLoading] = useState(false);
  const [jobsLoading, setJobsLoading] = useState(true);
  const [blockNotice, setBlockNotice] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [exportConfirm, setExportConfirm] = useState<{
    format: "docx" | "pdf";
    mode: "application" | "diagnostic";
    reason: "pending" | "unlinked";
    pending: number;
  } | null>(null);
  const [reviewMode, setReviewMode] = useState(false);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [editing, setEditing] = useState(false);
  const [draftHistory, setDraftHistory] = useState<ResumeDraftSummary[]>([]);

  async function refreshJobs() {
    setJobsLoading(true);
    try {
      const payload = await api.jobs();
      setJobs(payload.items);
      if (!jobId && payload.items[0]) setJobId(payload.items[0].id);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "加载岗位失败");
    } finally {
      setJobsLoading(false);
    }
  }

  async function loadPendingDraft() {
    const draftId = readPendingDraftId(localStorage);
    if (draftId == null) return;
    try {
      const draft = await api.getResumeDraft(draftId);
      localStorage.removeItem(PENDING_DRAFT_KEY);
      setDraft(draft);
      setJobId(draft.job_id);
      setReviewMode(false);
      setCurrentIndex(0);
      setEditing(false);
    } catch (error) {
      localStorage.removeItem(PENDING_DRAFT_KEY);
      toast.error(error instanceof Error ? error.message : "加载草稿失败");
    }
  }

  async function refreshDraftHistory(jobIdToFetch: number | "") {
    if (!jobIdToFetch) {
      setDraftHistory([]);
      return;
    }
    try {
      setDraftHistory(await api.listResumeDrafts(Number(jobIdToFetch)));
    } catch {
      setDraftHistory([]);
    }
  }

  useEffect(() => {
    void refreshJobs();
    void loadPendingDraft();
  }, []);

  useEffect(() => {
    setBlockNotice(null);
    void refreshDraftHistory(jobId);
  }, [jobId]);

  async function generate() {
    if (!jobId) return;
    setLoading(true);
    try {
      const newDraft = await api.createResumeDraft(Number(jobId));
      setDraft(newDraft);
      setBlockNotice(null);
      setReviewMode(false);
      setCurrentIndex(0);
      setEditing(false);
      void refreshDraftHistory(jobId);
      toast.success("已生成简历草稿");
    } catch (error) {
      const message = error instanceof Error ? error.message : "生成失败";
      // P0-2：硬性门槛阻断不再是几秒即逝的 toast + 死胡同空态，
      // 转为页面内常驻提示并给出「去岗位库」出口。
      const notice = mismatchNoticeFromError(message);
      setBlockNotice(notice);
      if (!notice) toast.error(message);
    } finally {
      setLoading(false);
    }
  }

  async function saveDraft(): Promise<boolean> {
    if (!draft) return false;
    try {
      const payload = await api.updateResumeDraft(draft.id, draft.sections);
      setDraft(payload);
      setSaved(true);
      window.setTimeout(() => setSaved(false), 1500);
      void refreshDraftHistory(jobId);
      return true;
    } catch (error) {
      // 保存失败不丢内容：本地编辑保留在 state 中，仅提示失败原因。
      toast.error(error instanceof Error ? `${error.message}（已编辑内容已保留，可重试保存）` : "保存失败，已编辑内容已保留，可重试保存");
      return false;
    }
  }

  function handleJobSelect(next: number) {
    if (next === jobId) return;
    if (shouldResetDraftOnJobChange(next, draft) &&
        !window.confirm("当前显示的是其他岗位的草稿，切换后将清除显示（历史版本仍可从「历史版本」恢复），确定切换吗？")) {
      return;
    }
    setJobId(next);
    setDraft(null);
    setReviewMode(false);
    setEditing(false);
    setCurrentIndex(0);
  }

  async function loadHistoricalDraft(draftId: number) {
    try {
      const loaded = await api.getResumeDraft(draftId);
      setDraft(loaded);
      setReviewMode(false);
      setCurrentIndex(0);
      setEditing(false);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "加载草稿失败");
    }
  }

  async function exportDraft(format: "docx" | "pdf", mode: "application" | "diagnostic" = "application") {
    if (!draft) return;
    const guard = exportBlock(draft.sections);
    if (guard.kind === "confirm") {
      setExportConfirm({ format, mode, reason: "pending", pending: guard.pending });
      return;
    }
    // B3：投递版导出前，未绑定档案证据的条目必须显式确认（后端另有 409 兜底）。
    if (mode === "application") {
      const unlinked = unlinkedExportCount(draft.sections);
      if (unlinked > 0) {
        setExportConfirm({ format, mode, reason: "unlinked", pending: unlinked });
        return;
      }
    }
    await doExport(format, mode, false);
  }

  async function doExport(format: "docx" | "pdf", mode: "application" | "diagnostic", override: boolean) {
    if (!draft) return;
    setExporting(true);
    setExportConfirm(null);
    try {
      const savedOk = await saveDraft();
      if (!savedOk) {
        toast.info("导出已中止：草稿保存失败，请先重试保存");
        return;
      }
      const { blob, filename } = await api.exportResume(draft.id, format, mode, override);
      downloadBlob(blob, filename ?? `resume-${draft.id}-${mode}.${format}`);
      toast.success(`已导出 ${format.toUpperCase()}`);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "导出失败");
    } finally {
      setExporting(false);
    }
  }

  /**
   * 确认「未审阅」后不直接导出：若同时存在无证据条目，继续走第二道确认，
   * 与后端两道独立 409 护栏保持一致，避免一次确认放行两道闸。
   */
  function confirmExportOverride() {
    if (!exportConfirm) return;
    if (exportConfirm.reason === "pending" && exportConfirm.mode === "application" && draft) {
      const unlinked = unlinkedExportCount(draft.sections);
      if (unlinked > 0) {
        setExportConfirm({ ...exportConfirm, reason: "unlinked", pending: unlinked });
        return;
      }
    }
    void doExport(exportConfirm.format, exportConfirm.mode, true);
  }

  function updateSectionTitle(index: number, value: string) {
    setDraft((current) => {
      if (!current) return current;
      const sections = [...current.sections];
      sections[index] = { ...sections[index], title: value };
      return { ...current, sections };
    });
  }

  function updateItem(sectionIndex: number, itemIndex: number, value: string) {
    setDraft((current) => {
      if (!current) return current;
      const sections: ResumeSection[] = current.sections.map((section, index) => {
        if (index !== sectionIndex) return section;
        const items = section.items.map((item, innerIndex) => (innerIndex === itemIndex ? { ...item, text: value } : item));
        return { ...section, items };
      });
      return { ...current, sections };
    });
  }

  // ── Review mode helpers ──────────────────────────────────────────

  const reviewItems = draft ? flattenReviewItems(draft.sections) : [];
  const totalItems = reviewItems.length;
  const currentItem = reviewItems[currentIndex];
  const draftStatus = draft ? computeDraftStatus(draft.sections) : "draft";

  function enterReview() {
    setReviewMode(true);
    setCurrentIndex(0);
    setEditing(false);
  }

  function exitReview() {
    setReviewMode(false);
    setEditing(false);
  }

  function setDecision(sectionId: string, itemIndex: number, decision: "adopt" | "edit" | "remove") {
    setDraft((current) => {
      if (!current) return current;
      const sections = current.sections.map((section) => {
        if (section.id !== sectionId) return section;
        const items = section.items.map((item, i) => (i === itemIndex ? { ...item, decision } : item));
        return { ...section, items };
      });
      return { ...current, sections };
    });
  }

  function startEdit() {
    if (!currentItem) return;
    setEditing(true);
    setDecision(currentItem.sectionId, currentItem.itemIndex, "edit");
  }

  function updateReviewText(sectionId: string, itemIndex: number, value: string) {
    setDraft((current) => {
      if (!current) return current;
      const sections = current.sections.map((section) => {
        if (section.id !== sectionId) return section;
        const items = section.items.map((item, i) =>
          i === itemIndex ? { ...item, text: value, decision: "edit" as const } : item,
        );
        return { ...section, items };
      });
      return { ...current, sections };
    });
  }

  function prev() {
    setEditing(false);
    setCurrentIndex((i) => Math.max(0, i - 1));
  }

  function next() {
    setEditing(false);
    setCurrentIndex((i) => Math.min(totalItems - 1, i + 1));
  }

  async function completeReview() {
    if (!draft) return;
    // B3：完成审阅 ≠ 全部采纳。存在未决策条目时拒绝完成并定位到第一项，
    // 不再把未决策项静默置为 adopt。
    const completion = reviewCompletion(draft.sections);
    if (completion.kind === "blocked") {
      setCurrentIndex(completion.firstPendingIndex);
      toast.info(`还有 ${completion.pending} 项待确认，已定位到第一项，请逐项决策后再完成审阅`);
      return;
    }
    try {
      const payload = await api.updateResumeDraft(draft.id, draft.sections);
      setDraft(payload);
      setReviewMode(false);
      setEditing(false);
      void refreshDraftHistory(jobId);
      toast.success("审阅完成，草稿可导出");
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "保存失败");
    }
  }

  // ── Derived review values ─────────────────────────────────────────

  const tone = currentItem ? reviewTone(currentItem, draft?.evidence ?? []) : "red";
  const toneStyle = TONE_STYLES[tone];
  const matchedEvidence =
    currentItem?.profile_field_id && draft
      ? draft.evidence.find((e) => e.profile_field_id === currentItem.profile_field_id)
      : undefined;
  const matchedTerms =
    matchedEvidence && Array.isArray(matchedEvidence.matched_terms)
      ? matchedEvidence.matched_terms.map(String)
      : [];

  // B6: Skeleton for resume editor when loading/generating
  const editorSkeleton = (
    <section className="panel resume-editor" aria-hidden="true">
      <div className="panel-head">
        <div className="skeleton skeleton-title" />
      </div>
      <div className="section-editor-list stagger-children">
        {Array.from({ length: 3 }, (_, i) => (
          <div className="section-editor" key={`es-${i}`}>
            <div className="skeleton skeleton-text" style={{ width: "40%", marginBottom: "10px" }} />
            <div className="skeleton skeleton-text" style={{ width: "90%", marginBottom: "6px" }} />
            <div className="skeleton skeleton-text" style={{ width: "85%", marginBottom: "6px" }} />
            <div className="skeleton skeleton-text" style={{ width: "70%" }} />
          </div>
        ))}
      </div>
      <span className="sr-only">生成中…</span>
    </section>
  );

  return (
    <div className="page-stack">
      <div className="toolbar">
        <div>
          <h1>简历生成</h1>
          <p className="subtle">岗位要求、履历证据、缺口提醒</p>
        </div>
        <button className="secondary-button" onClick={refreshJobs}>
          <RefreshCcw size={17} />
          刷新岗位
        </button>
      </div>

      <section className="panel">
        <div className="generator-row">
          <label>
            <span>目标岗位</span>
            <select value={jobId} onChange={(event) => handleJobSelect(Number(event.target.value))}>
              {jobsLoading ? (
                <option value="">加载中…</option>
              ) : jobs.length === 0 ? (
                <option value="">暂无岗位</option>
              ) : (
                jobs.map((job) => (
                  <option value={job.id} key={job.id}>
                    {job.institution_name} / {job.title}
                  </option>
                ))
              )}
            </select>
          </label>
          {/* Task C: 生成是本页主 CTA */}
          <button className="primary-button" onClick={generate} disabled={loading || !jobId || jobsLoading}>
            {loading ? <ButtonSpinner /> : <WandSparkles size={17} />}
            生成
          </button>
        </div>
      </section>

      {blockNotice && (
        <section className="panel block-notice" role="alert">
          <div className="block-notice-body">
            <strong>无法为该岗位生成简历草稿</strong>
            <p>{blockNotice}</p>
            <span className="small">学历等硬性条件由公告原文判定；匹配度列只统计履历可比的要求，可据此挑选岗位。</span>
          </div>
          <button className="secondary-button" onClick={() => onNavigate?.("jobs")}>
            去岗位库按学历筛选
          </button>
        </section>
      )}

      {draftHistory.length > 0 && (
        <section className="panel">
          <div className="panel-head">
            <h2><History size={17} /> 历史版本</h2>
          </div>
          <div className="compact-list stagger-children">
            {draftHistory.map((item) => (
              <button
                key={item.id}
                className={`history-item${draft?.id === item.id ? " history-item-active" : ""}`}
                onClick={() => void loadHistoricalDraft(item.id)}
              >
                <span className="history-item-title">
                  <strong>#{item.id}</strong> {item.title}
                </span>
                <span className="history-item-meta">
                  <span className={`status ${item.status === "reviewed" ? "success" : "idle"}`}>
                    {item.status === "reviewed" ? "已审阅" : "草稿"}
                  </span>
                  <span className="history-item-time">
                    {item.updated_at.replace("T", " ").slice(0, 16)}
                  </span>
                </span>
              </button>
            ))}
          </div>
        </section>
      )}

      {loading ? (
        <div className="resume-layout">
          {editorSkeleton}
          <aside className="detail-panel">
            <div className="skeleton skeleton-title" style={{ marginBottom: "16px" }} />
            <div className="compact-list">
              {Array.from({ length: 3 }, (_, i) => (
                <div className="evidence-card" key={`ev-skel-${i}`}>
                  <div className="skeleton skeleton-text" style={{ width: "60%", marginBottom: "8px" }} />
                  <div className="skeleton skeleton-text" style={{ width: "100%" }} />
                </div>
              ))}
            </div>
            <span className="sr-only">生成中…</span>
          </aside>
        </div>
      ) : draft ? (
        <div className="resume-layout">
          <section className="panel resume-editor">
            <div className="panel-head">
              <h2>{draft.title}</h2>
              <div className="button-row">
                {reviewMode ? (
                  <button className="secondary-button" onClick={exitReview}>
                    <Pencil size={17} />
                    退出审阅
                  </button>
                ) : (
                  <button className="secondary-button" onClick={enterReview}>
                    <ListChecks size={17} />
                    分步审阅
                  </button>
                )}
                <button className="secondary-button" onClick={saveDraft}>
                  <Save size={17} />
                  {saved ? "已保存" : "保存"}
                </button>
                <button className="secondary-button" onClick={() => void exportDraft("docx")} disabled={exporting}>
                  {exporting ? <ButtonSpinner /> : <Download size={17} />}
                  {exporting ? "导出中..." : "投递 DOCX"}
                </button>
                <button className="secondary-button" onClick={() => void exportDraft("pdf")} disabled={exporting}>
                  {exporting ? <ButtonSpinner /> : <FileDown size={17} />}
                  {exporting ? "导出中..." : "投递 PDF"}
                </button>
                <button className="text-button" onClick={() => void exportDraft("docx", "diagnostic")} disabled={exporting}>
                  {exporting ? <ButtonSpinner /> : <Download size={17} />}
                  诊断 DOCX
                </button>
              </div>
            </div>

            {reviewMode ? (
              <div className="section-editor-list">
                <div style={{ marginBottom: "0.75rem", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                  <span style={{ fontWeight: 600 }}>
                    第 {currentIndex + 1}/{totalItems} 项
                  </span>
                  <span className={`status ${draftStatus === "reviewed" ? "success" : "idle"}`}>
                    {draftStatus === "reviewed" ? "已审阅" : "草稿"}
                  </span>
                </div>

                {currentItem && (
                  <div
                    style={{
                      marginBottom: "1rem",
                      padding: "0.75rem",
                      background: toneStyle.bg,
                      borderRadius: "6px",
                      border: `1px solid ${toneStyle.border}`,
                    }}
                  >
                    <div style={{ fontWeight: 600, color: toneStyle.color, marginBottom: "0.25rem" }}>
                      {toneStyle.label}：{currentItem.sectionTitle}
                    </div>

                    {editing ? (
                      <textarea
                        style={{ width: "100%", minHeight: "4rem", marginBottom: "0.5rem" }}
                        value={currentItem.text}
                        onChange={(event) => updateReviewText(currentItem.sectionId, currentItem.itemIndex, event.target.value)}
                      />
                    ) : (
                      <div style={{ fontSize: "0.85rem", color: "#374151", marginBottom: "0.5rem" }}>
                        {currentItem.decision === "remove" ? (
                          <span style={{ textDecoration: "line-through", opacity: 0.6 }}>{currentItem.text}</span>
                        ) : (
                          currentItem.text
                        )}
                      </div>
                    )}

                    {currentItem.decision && (
                      <div style={{ fontSize: "0.75rem", marginTop: "0.25rem" }}>
                        决策：{DECISION_LABEL[currentItem.decision] ?? currentItem.decision}
                      </div>
                    )}

                    {currentItem.profile_field_id && (
                      <div className="evidence-chain" style={{ marginTop: "0.5rem", display: "flex", alignItems: "center", gap: "0.4rem", flexWrap: "wrap" }}>
                        <span style={{ fontSize: "0.75rem", color: "#6b7280" }}>档案:{currentItem.profile_field_id}</span>
                        {matchedTerms.length > 0 && (
                          <div className="tag-row evidence-terms" style={{ display: "flex", gap: "0.25rem" }}>
                            {matchedTerms.map((term) => (
                              <span className="tag" key={term}>{term}</span>
                            ))}
                          </div>
                        )}
                      </div>
                    )}

                    {isUnlinkedReviewItem(currentItem, currentItem.sectionId) && (
                      <div style={{ marginTop: "0.5rem" }}>
                        <span className="status danger">无档案证据关联</span>
                      </div>
                    )}

                    <div style={{ marginTop: "0.5rem", display: "flex", gap: "0.5rem" }}>
                      <button
                        className="secondary-button"
                        style={{ fontSize: "0.75rem" }}
                        onClick={() => {
                          setEditing(false);
                          setDecision(currentItem.sectionId, currentItem.itemIndex, "adopt");
                        }}
                      >
                        <CheckCircle2 size={15} />
                        采纳
                      </button>
                      <button
                        className="secondary-button"
                        style={{ fontSize: "0.75rem" }}
                        onClick={startEdit}
                      >
                        <Pencil size={15} />
                        修改措辞
                      </button>
                      <button
                        className="text-button"
                        style={{ fontSize: "0.75rem" }}
                        onClick={() => {
                          setEditing(false);
                          setDecision(currentItem.sectionId, currentItem.itemIndex, "remove");
                        }}
                      >
                        <Trash2 size={15} />
                        删除
                      </button>
                    </div>
                  </div>
                )}

                <div className="button-row" style={{ marginTop: "0.75rem" }}>
                  <button className="secondary-button" onClick={prev} disabled={currentIndex === 0}>
                    <ChevronLeft size={17} />
                    上一项
                  </button>
                  <button className="secondary-button" onClick={next} disabled={currentIndex >= totalItems - 1}>
                    下一项
                    <ChevronRight size={17} />
                  </button>
                  {/* Task C: 完成审阅是审阅模式下的主 CTA */}
                  <button className="primary-button" onClick={() => void completeReview()}>
                    <CheckCircle2 size={17} />
                    完成审阅
                  </button>
                </div>
              </div>
            ) : (
              <div className="section-editor-list stagger-children">
                {draft.sections.map((section, sectionIndex) => (
                  <div className="section-editor" key={section.id}>
                    <input className="section-title-input" value={section.title} onChange={(event) => updateSectionTitle(sectionIndex, event.target.value)} />
                    {section.items.map((item, itemIndex) => (
                      <textarea key={`${section.id}-${itemIndex}`} value={item.text} onChange={(event) => updateItem(sectionIndex, itemIndex, event.target.value)} />
                    ))}
                  </div>
                ))}
              </div>
            )}
          </section>

          <aside className="detail-panel">
            <h2>证据</h2>
            <div className="compact-list evidence-list">
              {draft.evidence.length === 0 ? (
                <div className="empty-line">暂无匹配证据</div>
              ) : (
                draft.evidence.map((item, index) => {
                  const matchedTerms = Array.isArray(item.matched_terms) ? item.matched_terms.map(String) : [];
                  return (
                    <div className="evidence-card" key={`${item.profile_field_id}-${index}`}>
                      <div className="evidence-card-head">
                        <strong>{String(item.requirement)}</strong>
                        <span className={`status ${evidenceStrengthTone(String(item.evidence_strength ?? ""))}`}>
                          {evidenceStrengthLabel(String(item.evidence_strength ?? ""))}
                        </span>
                      </div>
                      <span>{evidenceSourceLabel(item)}</span>
                      <p>{String(item.source_text)}</p>
                      {matchedTerms.length > 0 && (
                        <div className="tag-row evidence-terms">
                          {matchedTerms.map((term) => <span className="tag" key={term}>{term}</span>)}
                        </div>
                      )}
                    </div>
                  );
                })
              )}
            </div>
            <h2>缺口</h2>
            <div className="compact-list">
              {draft.gaps.length === 0 ? (
                <div className="empty-line">未发现明显缺口</div>
              ) : (
                draft.gaps.map((gap, index) => (
                  <div className={`gap-card${gap.blocking ? " gap-card-blocking" : ""}`} key={`${gap.requirement}-${index}`}>
                    {gap.blocking && <strong className="gap-blocking-label">硬性条件不满足</strong>}
                    {gap.message}
                  </div>
                ))
              )}
            </div>
          </aside>
        </div>
      ) : (
        <section className="panel">
          <div className="empty-state">
            <WandSparkles size={32} />
            <p>选择目标岗位后点击「生成」，系统将基于您的履历和岗位要求生成定制简历草稿</p>
            <span className="small">生成的草稿可编辑、审阅、导出 DOCX/PDF</span>
          </div>
        </section>
      )}

      {exportConfirm && (
        <div className="modal-overlay" style={{
          position: "fixed", inset: 0, background: "rgba(0,0,0,0.4)",
          display: "flex", alignItems: "center", justifyContent: "center", zIndex: 1000,
        }}>
          <div className="panel" style={{ maxWidth: 480, padding: "1.5rem" }}>
            <h2 style={{ marginBottom: "0.5rem" }}>
              {exportConfirm.reason === "pending" ? "草稿尚未审阅完成" : "存在未关联档案证据的内容"}
            </h2>
            <p className="subtle" style={{ marginBottom: "1rem" }}>
              {exportConfirm.reason === "pending"
                ? `还有 ${exportConfirm.pending} 项待确认。未审阅的草稿可能包含不完整或待修改的内容，是否继续导出？`
                : `有 ${exportConfirm.pending} 项内容未关联档案证据（可能为手动添加），导出后无法追溯其来源。请确认这些内容真实无误后再继续。`}
            </p>
            <div className="button-row" style={{ justifyContent: "flex-end" }}>
              <button className="secondary-button" onClick={() => setExportConfirm(null)}>
                {exportConfirm.reason === "pending" ? "返回审阅" : "返回检查"}
              </button>
              <button
                className="primary-button"
                onClick={confirmExportOverride}
                disabled={exporting}
              >
                {exporting && <ButtonSpinner />}
                {exporting ? "导出中..." : "继续导出"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
