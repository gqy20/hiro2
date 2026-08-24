import type { Evidence } from "@/lib/job-update";

export type SkillMatch = {
  name: string;
  level: string;
  years: number;
  status: "ready" | "partial" | "missing";
  evidence: string;
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
    projects: string[];
  };
  job: {
    title: string;
    version: string;
    window: string;
    evidenceCount: number;
  };
  report: {
    matchId: string;
    algorithmVersion: string;
    overallScore: number;
    evidence: Evidence[];
    gaps: Array<{
      skill: string;
      reason: string;
      priority: "high" | "medium";
      action: string;
    }>;
  };
};
