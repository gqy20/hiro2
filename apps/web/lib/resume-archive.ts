export type ResumeParseStats = {
  totalSkills: number;
  resolved: number;
  byDict: number;
  byLlm: number;
  unresolved: number;
};

export type ResumeArchiveItem = {
  resume_id: string;
  filename: string;
  size: number;
  suffix: string;
  uploaded_at: string;
  source: string;
  sample_type: "synthetic" | "anonymized" | "uploaded" | "controlled";
  parse_mode?: "llm" | "deterministic_fallback" | "shared_case_profile" | "";
  parse_error?: string;
  stats: ResumeParseStats | null;
};

export type ResumeArchiveDetail = {
  resumeId: string;
  filename: string;
  size: number;
  suffix?: string;
  uploadedAt: string;
  source: string;
  sampleType: ResumeArchiveItem["sample_type"];
  parseMode?: ResumeArchiveItem["parse_mode"];
  parseError?: string;
  profileSourceResumeId?: string;
  rawText: string;
  profile: {
    education?: string;
    experience_years?: number | null;
    location?: string;
    work_experiences?: Array<{
      company: string;
      title: string;
      start_date: string;
      end_date: string;
      summary: string;
      achievements: string[];
      skill_mentions: string[];
    }>;
    education_history?: Array<{
      school: string;
      major: string;
      degree: string;
      start_date: string;
      end_date: string;
    }>;
    certificates?: Array<{ name: string; issuer: string; issued_date: string }>;
    portfolio_urls?: string[];
    languages?: string[];
    skills?: Array<{
      mention: string;
      skill_id: string | null;
      proficiency: string;
      resolved_by: string;
      reason: string;
    }>;
    projects?: Array<{ name: string; description: string }>;
  };
  stats: ResumeParseStats | null;
};

export const MOCK_RESUME_ARCHIVE: ResumeArchiveItem[] = [
  {
    resume_id: "res-mock-01",
    filename: "div_variant_agent_00.pdf",
    size: 184_320,
    suffix: ".pdf",
    uploaded_at: "2026-08-27T10:00:00",
    source: "imported",
    sample_type: "synthetic",
    parse_mode: "llm",
    stats: {
      totalSkills: 12,
      resolved: 11,
      byDict: 9,
      byLlm: 2,
      unresolved: 1,
    },
  },
  {
    resume_id: "res-mock-02",
    filename: "div_buried_career_change_11.pdf",
    size: 165_100,
    suffix: ".pdf",
    uploaded_at: "2026-08-26T18:30:00",
    source: "imported",
    sample_type: "synthetic",
    parse_mode: "",
    stats: null,
  },
  {
    resume_id: "res-mock-03",
    filename: "div_noisy_llm_12.docx",
    size: 98_304,
    suffix: ".docx",
    uploaded_at: "2026-08-26T18:30:00",
    source: "imported",
    sample_type: "synthetic",
    parse_mode: "",
    stats: null,
  },
];
