import type {
 AnalyticsSummary,
 CrawlRun,
 Institution,
 JobDetail,
 JobList,
 NotificationItem,
 Profile,
 ProfileImportResult,
 Report,
 ResumeDraft,
 ResumeDraftSummary,
 ResumeSection,
 JobUserStatus,
 Subscription
} from "../types";
import type {
  FieldReferenceResult,
  OverlapCheckResult
} from "./profileChecks";

const API_BASE = import.meta.env.VITE_API_BASE ?? "";
const TOKEN_KEY = "auth_token";

export class UnauthorizedError extends Error {
  constructor(message = "请先登录") {
    super(message);
    this.name = "UnauthorizedError";
  }
}

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string | null) {
  if (token) localStorage.setItem(TOKEN_KEY, token);
  else localStorage.removeItem(TOKEN_KEY);
}

let onUnauthorized: (() => void) | null = null;

export function setUnauthorizedHandler(handler: () => void) {
  onUnauthorized = handler;
}

function authHeaders(extra?: HeadersInit): HeadersInit {
  const token = getToken();
  return {
    ...(extra ?? {}),
    ...(token ? { Authorization: `Bearer ${token}` } : {})
  };
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: {
      "Content-Type": "application/json",
      ...authHeaders(options?.headers)
    },
    ...options
  });
  if (response.status === 401) {
    setToken(null);
    onUnauthorized?.();
    throw new UnauthorizedError(await errorMessage(response, "请先登录"));
  }
  if (!response.ok) {
    throw new Error(await errorMessage(response, `Request failed: ${response.status}`));
  }
  // 204 No Content（及约定外的空响应体）：直接返回 undefined，不再解析 JSON。
  if (response.status === 204) return undefined as T;
  const text = await response.text();
  if (!text) return undefined as T;
  return JSON.parse(text) as T;
}

async function errorMessage(response: Response, fallback: string): Promise<string> {
  const text = await response.text();
  if (!text) return fallback;
  try {
    const parsed = JSON.parse(text) as { detail?: unknown };
    if (typeof parsed.detail === "string") return parsed.detail;
    if (Array.isArray(parsed.detail)) return parsed.detail.map((item) => String(item.msg ?? item)).join("；");
  } catch {
    return text;
  }
  return text;
}

export const api = {
  register: (username: string, password: string) =>
    request<{ token: string; username: string }>("/api/auth/register", {
      method: "POST",
      body: JSON.stringify({ username, password })
    }),
  login: (username: string, password: string) =>
    request<{ token: string; username: string }>("/api/auth/login", {
      method: "POST",
      body: JSON.stringify({ username, password })
    }),
  me: () => request<{ username: string }>("/api/auth/me"),
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
  saveJobStatus: (jobId: number, payload: { status: string; note?: string | null; deadline?: string | null }) =>
    request<JobUserStatus>(`/api/jobs/${jobId}/status`, {
      method: "PUT",
      body: JSON.stringify(payload)
    }),
  clearJobStatus: async (jobId: number) => {
    const response = await fetch(`${API_BASE}/api/jobs/${jobId}/status`, {
      method: "DELETE",
      headers: authHeaders()
    });
    if (response.status === 401) {
      setToken(null);
      onUnauthorized?.();
      throw new UnauthorizedError();
    }
    if (!response.ok) throw new Error(await errorMessage(response, "清除状态失败"));
  },
  crawlRun: (id: number) => request<CrawlRun>(`/api/crawl-runs/${id}`),
  crawlRuns: (limit = 10) => request<CrawlRun[]>(`/api/crawl-runs?limit=${limit}`),
  institutionsHealth: () =>
    request<{ threshold: number; review_count: number; institutions: Institution[] }>(
      "/api/institutions/health"
    ),
  recrawlInstitution: (id: number) =>
    request<CrawlRun>(`/api/institutions/${id}/recrawl`, { method: "POST" }),
  notifications: (limit = 20) => request<NotificationItem[]>(`/api/notifications?limit=${limit}`),
  unreadCount: () => request<{ count: number }>("/api/notifications/unread-count"),
  markNotificationRead: (id: number) =>
    request<NotificationItem>(`/api/notifications/${id}/read`, { method: "POST" }),
  markAllNotificationsRead: () =>
    request<{ marked: number }>("/api/notifications/read-all", { method: "POST" }),
  analytics: (trust?: string) =>
    request<AnalyticsSummary>(`/api/analytics/summary${trust && trust !== "all" ? `?trust=${trust}` : ""}`),
  profile: () => request<Profile>("/api/profile"),
  saveProfile: (profile: Profile) =>
    request<Profile>("/api/profile", {
      method: "PUT",
      body: JSON.stringify(profile)
    }),
  checkFieldReferences: (fieldId: string) =>
    request<FieldReferenceResult>(
      `/api/profile/field-references?field_id=${encodeURIComponent(fieldId)}`
    ),
  checkOverlap: (profile: Profile) =>
    request<OverlapCheckResult>("/api/profile/check-overlap", {
      method: "POST",
      body: JSON.stringify(profile)
    }),
  importProfile: async (file: File) => {
    const form = new FormData();
    form.append("file", file);
    const response = await fetch(`${API_BASE}/api/profile/import`, {
      method: "POST",
      headers: authHeaders(),
      body: form
    });
    if (response.status === 401) {
      setToken(null);
      onUnauthorized?.();
      throw new UnauthorizedError();
    }
    if (!response.ok) throw new Error(await errorMessage(response, "导入失败"));
    return (await response.json()) as ProfileImportResult;
  },
  createResumeDraft: (jobId: number) =>
    request<ResumeDraft>("/api/resume-drafts", {
      method: "POST",
      body: JSON.stringify({ job_id: jobId })
    }),
  getResumeDraft: (draftId: number) =>
    request<ResumeDraft>(`/api/resume-drafts/${draftId}`),
  listResumeDrafts: (jobId?: number) => {
    const query = new URLSearchParams();
    if (jobId != null) query.set("job_id", String(jobId));
    return request<ResumeDraftSummary[]>(`/api/resume-drafts${query.toString() ? `?${query}` : ""}`);
  },
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
  subscriptions: () => request<Subscription[]>("/api/subscriptions"),
  createSubscription: (payload: { name: string; keyword: string; institution_ids?: number[] }) =>
    request<Subscription>("/api/subscriptions", {
      method: "POST",
      body: JSON.stringify(payload)
    }),
  deleteSubscription: (id: number) =>
    request<void>(`/api/subscriptions/${id}`, { method: "DELETE" }),
  markSubscriptionRead: (id: number) =>
    request<Subscription>(`/api/subscriptions/${id}/mark-read`, { method: "POST" }),
  scanSubscriptions: () =>
    request<{ scanned: number; pushed: number }>("/api/subscriptions/scan", { method: "POST" }),
  exportResume: async (
    draftId: number,
    format: "docx" | "pdf",
    mode: "application" | "diagnostic" = "application",
    override = false,
  ): Promise<{ blob: Blob; filename: string | null }> => {
    const params = new URLSearchParams({ format, mode, override: String(override) });
    const response = await fetch(`${API_BASE}/api/resume-drafts/${draftId}/export?${params}`, {
      method: "POST",
      headers: authHeaders()
    });
    if (response.status === 401) {
      setToken(null);
      onUnauthorized?.();
      throw new UnauthorizedError();
    }
    if (!response.ok) throw new Error(await errorMessage(response, "导出失败"));
    const filename = parseContentDispositionFilename(response.headers.get("Content-Disposition"));
    return { blob: await response.blob(), filename };
  }
};

export function parseContentDispositionFilename(disposition: string | null): string | null {
  if (!disposition) return null;
  const starMatch = disposition.match(/filename\*=UTF-8''([^;]+)/i);
  if (starMatch) {
    try {
      return decodeURIComponent(starMatch[1]);
    } catch {
      return starMatch[1];
    }
  }
  const plainMatch = disposition.match(/filename="?([^";]+)"?/i);
  if (plainMatch) return plainMatch[1].trim();
  return null;
}

export function downloadBlob(blob: Blob, fileName: string) {
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = fileName;
  anchor.click();
  URL.revokeObjectURL(url);
}
