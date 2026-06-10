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
};

export type JobList = {
  total: number;
  items: Job[];
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
  basic: Record<string, string>;
  education: Array<Record<string, unknown>>;
  experiences: Array<Record<string, unknown>>;
  projects: Array<Record<string, unknown>>;
  publications: Array<Record<string, unknown>>;
  certificates: Array<Record<string, unknown>>;
  skills: Array<Record<string, unknown>>;
  teaching: Array<Record<string, unknown>>;
  awards: Array<Record<string, unknown>>;
  languages: Array<Record<string, unknown>>;
  updated_at?: string | null;
};

export type ResumeSection = {
  id: string;
  title: string;
  items: Array<{
    text: string;
    profile_field_id?: string;
    evidence_level?: string;
  }>;
};

export type ResumeDraft = {
  id: number;
  job_id: number;
  profile_id: string;
  title: string;
  sections: ResumeSection[];
  evidence: Array<Record<string, unknown>>;
  gaps: Array<{ requirement: string; message: string }>;
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
