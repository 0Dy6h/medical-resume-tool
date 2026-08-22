import { CheckCircle2, ChevronLeft, ChevronRight, Download, FileDown, ListChecks, Pencil, RefreshCcw, Save, Trash2, WandSparkles } from "lucide-react";
import { useEffect, useState } from "react";
import { useToast } from "../components/Toast";
import { api, downloadBlob } from "../lib/api";
import { evidenceSourceLabel, evidenceStrengthLabel, evidenceStrengthTone } from "../lib/resumeEvidence";
import type { Job, ResumeDraft, ResumeSection } from "../types";

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

export function ResumePage() {
  const toast = useToast();
  const [jobs, setJobs] = useState<Job[]>([]);
  const [jobId, setJobId] = useState<number | "">("");
  const [draft, setDraft] = useState<ResumeDraft | null>(null);
  const [loading, setLoading] = useState(false);
  const [saved, setSaved] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [reviewMode, setReviewMode] = useState(false);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [editing, setEditing] = useState(false);

  async function refreshJobs() {
    try {
      const payload = await api.jobs();
      setJobs(payload.items);
      if (!jobId && payload.items[0]) setJobId(payload.items[0].id);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "加载岗位失败");
    }
  }

  useEffect(() => {
    void refreshJobs();
  }, []);

  async function generate() {
    if (!jobId) return;
    setLoading(true);
    try {
      setDraft(await api.createResumeDraft(Number(jobId)));
      setReviewMode(false);
      setCurrentIndex(0);
      setEditing(false);
      toast.success("已生成简历草稿");
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "生成失败");
    } finally {
      setLoading(false);
    }
  }

  async function saveDraft() {
    if (!draft) return;
    const payload = await api.updateResumeDraft(draft.id, draft.sections);
    setDraft(payload);
    setSaved(true);
    window.setTimeout(() => setSaved(false), 1500);
  }

  async function exportDraft(format: "docx" | "pdf", mode: "application" | "diagnostic" = "application") {
    if (!draft) return;
    setExporting(true);
    try {
      await saveDraft();
      const blob = await api.exportResume(draft.id, format, mode);
      downloadBlob(blob, `resume-${draft.id}-${mode}.${format}`);
      toast.success(`已导出 ${format.toUpperCase()}`);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "导出失败");
    } finally {
      setExporting(false);
    }
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
    const sections = draft.sections.map((section) => ({
      ...section,
      items: section.items.map((item) => ({
        ...item,
        decision: item.decision ?? ("adopt" as const),
      })),
    }));
    try {
      const payload = await api.updateResumeDraft(draft.id, sections);
      setDraft(payload);
      setReviewMode(false);
      setEditing(false);
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

  return (
    <div className="page-stack">
      <div className="toolbar">
        <div>
          <h1>简历生成</h1>
          <p className="subtle">岗位要求、履历证据、缺口提醒</p>
        </div>
        <button className="icon-text-button" onClick={refreshJobs}>
          <RefreshCcw size={17} />
          刷新岗位
        </button>
      </div>

      <section className="panel">
        <div className="generator-row">
          <label>
            <span>目标岗位</span>
            <select value={jobId} onChange={(event) => setJobId(Number(event.target.value))}>
              {jobs.map((job) => (
                <option value={job.id} key={job.id}>
                  {job.institution_name} / {job.title}
                </option>
              ))}
            </select>
          </label>
          <button className="primary-button" onClick={generate} disabled={loading || !jobId}>
            <WandSparkles size={17} />
            生成
          </button>
        </div>
      </section>

      {draft && (
        <div className="resume-layout">
          <section className="panel resume-editor">
            <div className="panel-head">
              <h2>{draft.title}</h2>
              <div className="button-row">
                {reviewMode ? (
                  <button className="icon-text-button" onClick={exitReview}>
                    <Pencil size={17} />
                    退出审阅
                  </button>
                ) : (
                  <button className="icon-text-button" onClick={enterReview}>
                    <ListChecks size={17} />
                    分步审阅
                  </button>
                )}
                <button className="icon-text-button" onClick={saveDraft}>
                  <Save size={17} />
                  {saved ? "已保存" : "保存"}
                </button>
                <button className="icon-text-button" onClick={() => void exportDraft("docx")} disabled={exporting}>
                  <Download size={17} />
                  {exporting ? "导出中..." : "投递 DOCX"}
                </button>
                <button className="icon-text-button" onClick={() => void exportDraft("pdf")} disabled={exporting}>
                  <FileDown size={17} />
                  {exporting ? "导出中..." : "投递 PDF"}
                </button>
                <button className="icon-text-button" onClick={() => void exportDraft("docx", "diagnostic")} disabled={exporting}>
                  <Download size={17} />
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

                    <div style={{ marginTop: "0.5rem", display: "flex", gap: "0.5rem" }}>
                      <button
                        className="icon-text-button"
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
                        className="icon-text-button"
                        style={{ fontSize: "0.75rem" }}
                        onClick={startEdit}
                      >
                        <Pencil size={15} />
                        修改措辞
                      </button>
                      <button
                        className="icon-text-button"
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
                  <button className="icon-text-button" onClick={prev} disabled={currentIndex === 0}>
                    <ChevronLeft size={17} />
                    上一项
                  </button>
                  <button className="icon-text-button" onClick={next} disabled={currentIndex >= totalItems - 1}>
                    下一项
                    <ChevronRight size={17} />
                  </button>
                  <button className="primary-button" onClick={() => void completeReview()}>
                    <CheckCircle2 size={17} />
                    完成审阅
                  </button>
                </div>
              </div>
            ) : (
              <div className="section-editor-list">
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
      )}
    </div>
  );
}
