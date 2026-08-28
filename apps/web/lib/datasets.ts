export type DatasetSource = {
  id: string;
  type: string;
  time_range: string[];
  ingestion_mode: string;
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
};

export type DatasetOverview = {
  total_datasets: number;
  total_records: number;
  ready_datasets: number;
  pending_records: number;
  datasets: DatasetItem[];
};
