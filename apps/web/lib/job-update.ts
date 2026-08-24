export type ReviewStatus =
  "reviewing" | "accepted" | "rejected" | "needs_evidence";
export type ChangeKind = "added" | "removed" | "modified";
export type SourceType = "招聘 JD" | "技术日报" | "职业标准";
export type EvidenceStance = "支持" | "反证";

export type Evidence = {
  id: string;
  source: string;
  sourceType: SourceType;
  publishedAt: string;
  collectedAt: string;
  quality: number;
  excerpt: string;
  fullText: string;
  sourceUrl: string | null;
  stance: EvidenceStance;
};

export type ChangeItem = {
  id: string;
  kind: ChangeKind;
  title: string;
  detail: string;
  confidence: number;
  status: ReviewStatus;
  evidence: Evidence[];
};

export type ProgressStep = {
  id: string;
  label: string;
  detail: string;
  state: "finished" | "active" | "waiting";
};

export type JobUpdateContext = {
  jobTitle: string;
  baselineVersion: string;
  targetVersion: string;
  timeWindow: string;
};

export type JobUpdateFixture = {
  fixtureVersion: string;
  mode: "synthetic";
  run: { id: string; datasetVersion: string; status: "REVIEWING" };
  context: JobUpdateContext;
  summary: { validSamples: number; companies: number; evidenceSources: number };
  changes: ChangeItem[];
  progressSteps: ProgressStep[];
};
