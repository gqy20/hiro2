export type DatasetSource = {
  id: string;
  type: string;
  time_range: string[];
  ingestion_mode: string;
  license: string;
  notes: string;
};

export type DatasetItem = {
  id: string;
  name: string;
  category: string;
  records: number;
  valid_records: number;
  version: string;
  status: string;
  formats: string[];
  source: string;
  updated_at: string;
  quality: number;
  sources?: DatasetSource[];
  count_scope: string;
  stage_counts: Array<{ stage: string; label: string; count: number }>;
};

export type DatasetOverview = {
  total_datasets: number;
  total_records: number;
  ready_datasets: number;
  pending_records: number;
  datasets: DatasetItem[];
};

export type DatasetVersion = {
  dataset_id: string;
  version: string;
  status: string;
  records: number;
  valid_records: number;
  pending_records: number;
  quality: number;
  manifest_hash: string;
  manifest: Record<string, unknown>;
  run_id: string;
  imported_at: string;
};

export type DatasetDetail = {
  dataset: DatasetItem;
  versions: DatasetVersion[];
};

export type DatasetSourceDetail = {
  dataset_id: string;
  dataset_version: string;
  source: DatasetSource;
  stats: {
    evidence_count: number;
    reviewed_evidence_count: number | null;
    average_quality: number | null;
    latest_evidence_at: string;
    claim_types: Record<string, number>;
    attribution: "exact" | "unavailable";
    attribution_note: string;
  };
};
