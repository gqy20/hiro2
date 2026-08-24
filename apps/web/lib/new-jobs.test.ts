import { describe, expect, it } from "vitest";

import ready from "../../../data/fixtures/new_jobs.json";
import empty from "../../../data/fixtures/new_jobs_empty.json";

describe("new job fixtures", () => {
  it("contains five definition fields and evidence for every candidate", () => {
    expect(ready.candidates.length).toBeGreaterThan(0);
    for (const candidate of ready.candidates) {
      expect(candidate.title).toBeTruthy();
      expect(candidate.responsibilities.length).toBeGreaterThan(0);
      expect(candidate.requiredSkills.length).toBeGreaterThan(0);
      expect(candidate.preferredSkills.length).toBeGreaterThan(0);
      expect(candidate.scenarios.length).toBeGreaterThan(0);
      expect(candidate.evidence.length).toBeGreaterThan(0);
    }
  });

  it("contains an explicit empty state fixture", () => {
    expect(empty.candidates).toHaveLength(0);
    expect(empty.mode).toBe("synthetic");
  });
});
