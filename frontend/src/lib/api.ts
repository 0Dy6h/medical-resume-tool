import type {
  AnalyticsSummary,
  CrawlRun,
  Institution,
  JobDetail,
  JobList,
  Profile,
  ProfileImportResult,
  Report,
  ResumeDraft,
  ResumeSection
} from "../types";

const API_BASE = import.meta.env.VITE_API_BASE ?? "";

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: {
      "Content-Type": "application/json",
      ...(options?.headers ?? {})
    },
    ...options
  });
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || `Request failed: ${response.status}`);
  }
  return (await response.json()) as T;
}

export const api = {
  institutions: () => request<Institution[]>("/api/institutions"),
  startCrawl: (institutionIds?: number[]) =>
    request<CrawlRun>("/api/crawl-runs", {
      method: "POST",
      body: JSON.stringify({ institution_ids: institutionIds?.length ? institutionIds : null })
    }),
  jobs: (params: Record<string, string | number | undefined> = {}) => {
    const query = new URLSearchParams();
    Object.entries(params).forEach(([key, value]) => {
      if (value !== undefined && value !== "") query.set(key, String(value));
    });
    return request<JobList>(`/api/jobs${query.toString() ? `?${query}` : ""}`);
  },
  job: (id: number) => request<JobDetail>(`/api/jobs/${id}`),
  crawlRun: (id: number) => request<CrawlRun>(`/api/crawl-runs/${id}`),
  analytics: () => request<AnalyticsSummary>("/api/analytics/summary"),
  profile: () => request<Profile>("/api/profile"),
  saveProfile: (profile: Profile) =>
    request<Profile>("/api/profile", {
      method: "PUT",
      body: JSON.stringify(profile)
    }),
  importProfile: async (file: File) => {
    const form = new FormData();
    form.append("file", file);
    const response = await fetch(`${API_BASE}/api/profile/import`, {
      method: "POST",
      body: form
    });
    if (!response.ok) throw new Error(await response.text());
    return (await response.json()) as ProfileImportResult;
  },
  createResumeDraft: (jobId: number) =>
    request<ResumeDraft>("/api/resume-drafts", {
      method: "POST",
      body: JSON.stringify({ job_id: jobId })
    }),
  updateResumeDraft: (draftId: number, sections: ResumeSection[]) =>
    request<ResumeDraft>(`/api/resume-drafts/${draftId}`, {
      method: "PUT",
      body: JSON.stringify({ sections })
    }),
  createReport: (title: string) =>
    request<Report>("/api/reports", {
      method: "POST",
      body: JSON.stringify({ title, filters: {} })
    }),
  exportResume: async (draftId: number, format: "docx" | "pdf") => {
    const response = await fetch(`${API_BASE}/api/resume-drafts/${draftId}/export?format=${format}`, {
      method: "POST"
    });
    if (!response.ok) throw new Error(await response.text());
    return response.blob();
  }
};

export function downloadBlob(blob: Blob, fileName: string) {
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = fileName;
  anchor.click();
  URL.revokeObjectURL(url);
}

