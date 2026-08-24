import { describe, expect, it } from "vitest";

import empty from "../../../data/fixtures/diagnosis_empty.json";
import error from "../../../data/fixtures/diagnosis_error.json";
import ready from "../../../data/fixtures/diagnosis.json";

describe("diagnosis fixtures", () => {
  it("contains candidate, published job context, and skill-level gaps", () => {
    expect(ready.candidate.id).toBeTruthy();
    expect(ready.job.version).toBe("v1.5");
    expect(ready.candidate.skills.map((skill) => skill.status)).toEqual(
      expect.arrayContaining(["ready", "partial", "missing"]),
    );
    expect(ready.report.gaps.length).toBeGreaterThan(0);
    expect(ready.report.evidence.length).toBeGreaterThan(0);
  });

  it("keeps an explicit empty fixture", () => {
    expect(empty.candidate.skills).toHaveLength(0);
    expect(empty.report.gaps).toHaveLength(0);
  });

  it("keeps an explicit error fixture without pretending to have a report", () => {
    expect(error.report.matchId).toBe("ERROR");
    expect(error.report.evidence).toHaveLength(0);
  });
});
