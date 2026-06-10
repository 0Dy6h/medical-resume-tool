import { Download, FileDown, RefreshCcw, Save, WandSparkles } from "lucide-react";
import { useEffect, useState } from "react";
import { api, downloadBlob } from "../lib/api";
import type { Job, ResumeDraft, ResumeSection } from "../types";

export function ResumePage() {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [jobId, setJobId] = useState<number | "">("");
  const [draft, setDraft] = useState<ResumeDraft | null>(null);
  const [loading, setLoading] = useState(false);
  const [saved, setSaved] = useState(false);
  const [exporting, setExporting] = useState(false);

  async function refreshJobs() {
    const payload = await api.jobs();
    setJobs(payload.items);
    if (!jobId && payload.items[0]) setJobId(payload.items[0].id);
  }

  useEffect(() => {
    void refreshJobs();
  }, []);

  async function generate() {
    if (!jobId) return;
    setLoading(true);
    try {
      setDraft(await api.createResumeDraft(Number(jobId)));
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

  async function exportDraft(format: "docx" | "pdf") {
    if (!draft) return;
    setExporting(true);
    try {
      await saveDraft();
      const blob = await api.exportResume(draft.id, format);
      downloadBlob(blob, `resume-${draft.id}.${format}`);
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
                <button className="icon-text-button" onClick={saveDraft}>
                  <Save size={17} />
                  {saved ? "已保存" : "保存"}
                </button>
                <button className="icon-text-button" onClick={() => void exportDraft("docx")} disabled={exporting}>
                  <Download size={17} />
                  {exporting ? "导出中..." : "DOCX"}
                </button>
                <button className="icon-text-button" onClick={() => void exportDraft("pdf")} disabled={exporting}>
                  <FileDown size={17} />
                  {exporting ? "导出中..." : "PDF"}
                </button>
              </div>
            </div>
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
          </section>

          <aside className="detail-panel">
            <h2>证据</h2>
            <div className="compact-list evidence-list">
              {draft.evidence.length === 0 ? (
                <div className="empty-line">暂无匹配证据</div>
              ) : (
                draft.evidence.map((item, index) => (
                  <div className="evidence-card" key={`${item.profile_field_id}-${index}`}>
                    <strong>{String(item.requirement)}</strong>
                    <span>{String(item.profile_field_id)}</span>
                    <p>{String(item.source_text)}</p>
                  </div>
                ))
              )}
            </div>
            <h2>缺口</h2>
            <div className="compact-list">
              {draft.gaps.length === 0 ? (
                <div className="empty-line">未发现明显缺口</div>
              ) : (
                draft.gaps.map((gap, index) => (
                  <div className="gap-card" key={`${gap.requirement}-${index}`}>{gap.message}</div>
                ))
              )}
            </div>
          </aside>
        </div>
      )}
    </div>
  );
}

