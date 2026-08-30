export type EvidenceSearchItem = {
  id: string;
  source: string;
  sourceType: string;
  publishedAt: string | null;
  collectedAt: string | null;
  quality: number;
  excerpt: string;
  fullText: string;
  sourceUrl: string | null;
  stance: string;
  claimType: string;
  reviewStatus: string;
};

export type EvidenceSearchResult = {
  items: EvidenceSearchItem[];
  total: number;
  offset: number;
  limit: number;
};

export type EvidenceFacetItem = {
  value: string;
  count: number;
};

export type EvidenceFacets = {
  sources: EvidenceFacetItem[];
  claimTypes: EvidenceFacetItem[];
  reviewStatuses: EvidenceFacetItem[];
  earliestPublishedAt: string;
  latestPublishedAt: string;
};
