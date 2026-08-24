import type { Evidence, ReviewStatus } from "@/lib/job-update";

export type EmergingJobCandidate = {
  id: string;
  title: string;
  summary: string;
  confidence: number;
  companies: number;
  sourceCount: number;
  status: ReviewStatus;
  whyNew: string;
  responsibilities: string[];
  requiredSkills: string[];
  preferredSkills: string[];
  scenarios: string[];
  evidence: Evidence[];
};

export type NewJobsFixture = {
  fixtureVersion: string;
  mode: "synthetic";
  runId: string;
  candidates: EmergingJobCandidate[];
};
