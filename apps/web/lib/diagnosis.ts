export type SkillMatch = {
  name: string;
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
    evidence: import("@/lib/job-update").Evidence[];
    gaps: Array<{
      skill: string;
      reason: string;
      priority: "high" | "medium";
      action: string;
    }>;
    career?: { completedSkills: string[]; proofs: Array<{ id: number; skill: string; title: string; description: string; url: string | null; createdAt: string }> };
  };
};
