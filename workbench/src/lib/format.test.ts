import { describe, expect, it } from "vitest";
import { formatRelevance, RELEVANCE_THRESHOLD } from "./format";

describe("formatRelevance", () => {
  it("uses backend default threshold 0.25", () => {
    expect(RELEVANCE_THRESHOLD).toBe(0.25);
    expect(formatRelevance(0.24)).toBe("低");
    expect(formatRelevance(0.25)).toBe("中");
    expect(formatRelevance(0.5)).toBe("高");
  });
});
