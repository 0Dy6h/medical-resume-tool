export type Institution = {
  id: number;
  name: string;
  institution_type: string;
  region: string;
  official_url: string;
  listing_url: string;
  crawl_strategy: string;
  enabled: boolean;
  last_crawled_at?: string | null;
  last_status?: string | null;
  last_error?: string | null;
  blocked_reason?: string | null;
};

export type CrawlRun = {
  id: number;
  status: string;
  started_at: string;
  completed_at?: string | null;
  institution_ids: number[];
  success_count: number;
  failure_count: number;
  error_summary: Array<Record<string, unknown>>;
  errors?: Array<Record<string, unknown>>;
  trigger?: "manual" | "auto";
};

export type JobMatch = {
  met: number;
  total: number;
  degree_percent: number;
  blocking_gap: boolean;
};

export type Job = {
  id: number;
  institution_id: number;
  institution_name: string;
  institution_type: string;
  region: string;
  title: string;
  department?: string | null;
  location?: string | null;
  education?: string | null;
  profession?: string | null;
  job_category: string;
  responsibilities?: string | null;
  requirements?: string | null;
  posted_at?: string | null;
  deadline?: string | null;
  source_url: string;
  source_text_hash: string;
  tags: string[];
  fetched_at: string;
  parser_name: string;
  confidence: number;
  data_trust?: "real" | "placeholder" | "fixture" | "disabled";
  user_status?: JobUserStatus | null;
  match?: JobMatch | null;
};

export type JobUserStatus = {
  job_id: number;
  status: "saved" | "evaluating" | "preparing" | "applied" | "archived" | string;
  note?: string | null;
  deadline?: string | null;
  created_at: string;
  updated_at: string;
};

export type MatchState = "met" | "partial" | "unmet" | "blocking";

export type MatchFinding = {
  requirement: string;
  status: MatchState;
  evidence: { source?: string; text?: string }[];
  advice?: string | null;
};

export type JobSnapshot = {
  source_text_hash: string;
  raw_text: string;
  parser_name: string;
  fetched_at: string;
  captured_at: string;
};

export type JobDetail = Job & {
  raw_snapshot: {
    source_url: string;
    source_text_hash: string;
    fetched_at: string;
    raw_text: string;
  };
  extraction_evidence: Record<string, unknown> & {
    attachments?: Array<Record<string, unknown>>;
    announcement_url?: string;
    attachment_url?: string;
    attachment_name?: string;
    sheet_name?: string;
    row_index?: number;
    headers?: string[];
    parser_warning?: string;
  };
  match_analysis?: MatchFinding[] | null;
  history?: JobSnapshot[];
};

export type JobList = {
  total: number;
  items: Job[];
  limit?: number;
  offset?: number;
};

export type CountItem = {
  name: string;
  count: number;
};

export type AnalyticsSummary = {
  totals: {
    jobs: number;
    institutions: number;
    regions: number;
    parsers: number;
    low_confidence_jobs: number;
    attachment_sourced_jobs: number;
    failed_attachment_events: number;
  };
  job_categories: CountItem[];
  education_levels: CountItem[];
  institution_types: CountItem[];
  regions: CountItem[];
  common_capabilities: CountItem[];
  institution_focus: Array<{
    institution: string;
    focus: CountItem[];
  }>;
  parser_quality: ParserQuality[];
  trust_breakdown?: CountItem[];
  generated_at?: string;
};

export type ParserQuality = {
  parser_name: string;
  jobs: number;
  low_confidence_jobs: number;
  attachment_sourced_jobs: number;
  failed_attachment_events: number;
  average_confidence: number;
  review_status: "review" | "watch" | "stable" | string;
};

export type Profile = {
  basics?: Record<string, unknown>;
  education: Array<Record<string, unknown>>;
  experiences: Array<Record<string, unknown>>;
  projects: Array<Record<string, unknown>>;
  publications: Array<Record<string, unknown>>;
  certificates: Array<Record<string, unknown>>;
  skills: Array<Record<string, unknown>>;
  teaching: Array<Record<string, unknown>>;
  awards: Array<Record<string, unknown>>;
  languages: Array<Record<string, unknown>>;
  mode?: "fresh_grad" | "experienced";
  updated_at?: string | null;
};

export type ReviewItem = {
  collection: string;
  item: Record<string, unknown>;
  source_text: string;
  confidence: number;
  warnings: string[];
};

export type UnassignedBlock = {
  text: string;
  reason: string;
};

export type ImportMeta = {
  source_type: string;
  extractor_name: string;
  text_quality: number;
  warnings: string[];
};

export type ProfileImportResult = Omit<Profile, "updated_at" | "basics"> & {
  basics?: Record<string, string>;
  review_items?: ReviewItem[];
  unassigned_blocks?: UnassignedBlock[];
  import_meta?: ImportMeta;
  warnings: string[];
};

export type ResumeSection = {
  id: string;
  title: string;
  items: Array<{
    text: string;
    profile_field_id?: string;
    evidence_level?: string;
    decision?: "adopt" | "edit" | "remove";
  }>;
};

export type ResumeDraft = {
  id: number;
  job_id: number;
  profile_id: string;
  title: string;
  sections: ResumeSection[];
  evidence: Array<Record<string, unknown>>;
  gaps: Array<{ requirement: string; message: string; blocking?: boolean }>;
  status?: string;
  created_at: string;
  updated_at: string;
};

export type ResumeDraftSummary = {
  id: number;
  job_id: number;
  title: string;
  status: string;
  created_at: string;
  updated_at: string;
};

export type Report = {
  id: number;
  title: string;
  markdown: string;
  html: string;
  filters: Record<string, unknown>;
  created_at: string;
};

export type SubscriptionInstitutionStatus = {
  id: number;
  name: string;
  is_maintenance: boolean;
};

export type Subscription = {
  id: number;
  name: string;
  keyword: string;
  institution_ids: number[];
  institution_statuses: SubscriptionInstitutionStatus[];
  new_count: number;
  last_checked_at: string;
  last_pushed_at: string | null;
  is_empty_30d: boolean;
  warning?: string | null;
  created_at: string;
};
