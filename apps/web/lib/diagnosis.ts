export type SkillMatch = {
  name: string;
  skillId?: string | null;
  pointId?: string | null;
  level: string;
  years: number | null;
  status: "ready" | "partial" | "missing";
  evidence: string;
};

export type ProjectEntry = {
  id: string;
  text: string;
};

export type UserCorrectionField =
  | "skill_status"
  | "skill_profile"
  | "project_text"
  | "project_added"
  | "project_removed";

export type UserCorrection = {
  id: string;
  timestamp: string;
  field: UserCorrectionField;
  target: string;
  before?: string;
  after?: string;
};

export type DiagnosisFixture = {
  fixtureVersion: string;
  mode: "synthetic";
  candidate: {
    id: string;
    name: string;
    headline: string;
    location: string;
    skills: SkillMatch[];
    projects: ProjectEntry[];
    userCorrections: UserCorrection[];
  };
  job: {
    title: string;
    version: string;
    window: string;
    evidenceCount: number;
  };
  targetJobs?: Array<{ version: string; title: string }>;
  report: {
    matchId: string;
    algorithmVersion: string;
    overallScore: number;
    requiredMet?: number;
    requiredTotal?: number;
    evidence?: import("@/lib/job-update").Evidence[];
    gaps: Array<{
      skill: string;
      reason: string;
      priority: "high" | "medium";
      action: string;
      practice?: string;
      evaluate?: string;
      certify?: string;
      certificates?: Array<{ name: string; issuer?: string; url?: string }>;
      contests?: Array<{
        name: string;
        organizer?: string;
        url?: string;
        status?: string;
        register_end?: string;
        days_left?: number | null;
      }>;
      trend?: {
        direction: string;
        confidence: number;
        emerging: boolean;
        note: string;
      } | null;
    }>;
    career?: {
      completedSkills: string[];
      proofs: Array<{
        id: number;
        skill: string;
        title: string;
        description: string;
        url: string | null;
        createdAt: string;
      }>;
    };
  };
};
