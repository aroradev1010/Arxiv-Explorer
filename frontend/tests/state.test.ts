import { describe, it, expect } from "vitest";
import {
  parseState,
  params,
  searchURL,
  paperURL,
  documentURL,
  authors,
  score,
  scoreLabel,
  querySchema,
  filterSchema,
  fusionSummary,
  canNext,
  dateLabel,
} from "@/lib/state";
import { normalizeError } from "@/lib/api/client";
import hybrid from "./fixtures/hybrid.json";
import type { RankedPaper } from "@/lib/api/types";
describe("backend contract presentation", () => {
  it("round trips scientific queries, filters and modes", () => {
    const state = {
      q: "GNN & α + β",
      mode: "bm25" as const,
      offset: 20,
      filters: {
        category: "cs.LG",
        author: "A & B",
        subject: "cs" as const,
        year_from: 2010,
        year_to: 2024,
      },
    };
    expect(
      parseState(new URLSearchParams(searchURL(state).split("?")[1])),
    ).toEqual(state);
    expect(params({ x: null, y: undefined, z: 0 }).toString()).toBe("z=0");
  });
  it("defaults bad mode and offset without dropping invalid filters", () => {
    expect(
      parseState(
        new URLSearchParams("mode=bad&offset=-1&year_from=2025&year_to=2000"),
      ),
    ).toMatchObject({ mode: "hybrid", offset: 0 });
    expect(
      filterSchema.safeParse(
        parseState(new URLSearchParams("year_from=2025&year_to=2000")).filters,
      ).success,
    ).toBe(false);
  });
  it("validates query and years", () => {
    for (const q of ["", "   ", "+++", "a".repeat(1001)])
      expect(querySchema.safeParse(q).success).toBe(false);
    expect(querySchema.safeParse("α + β").success).toBe(true);
    expect(filterSchema.safeParse({ year_from: 1990 }).success).toBe(false);
  });
  it("encodes legacy IDs and refuses unsafe external IDs", () => {
    expect(paperURL("hep-th/9901001")).toBe(
      "/papers?arxiv_id=hep-th%2F9901001",
    );
    expect(documentURL("hep-th/9901001", true)).toBe(
      "https://arxiv.org/pdf/hep-th/9901001",
    );
    expect(documentURL("https://evil.test")).toBe(null);
  });
  it("preserves raw author fallback and handles missing dates", () => {
    expect(
      authors({
        ...hybrid.results[0].paper,
        authors: [],
        authors_text: "Raw Collaboration",
        authors_source: "raw_only",
      }),
    ).toBe("Raw Collaboration");
    expect(dateLabel("nonsense")).toBe(null);
    expect(dateLabel("2025-02-31")).toBe(null);
    expect(dateLabel(null)).toBe(null);
  });
  it("formats native scores and verifies real RRF contributions", () => {
    const r = hybrid.results[0] as RankedPaper;
    expect(score(0.012345678, "hybrid")).toBe("0.012346");
    expect(scoreLabel("semantic")).toBe("Cosine similarity");
    expect(fusionSummary(r)).toMatchObject({ matches: true, k: 60 });
  });
  it("bounds pagination using has_more and the returned window", () => {
    expect(
      canNext({
        ...hybrid.pagination,
        offset: 190,
        limit: 10,
        ranking_window_size: 200,
        has_more: true,
      }),
    ).toBe(false);
    expect(canNext({ ...hybrid.pagination, offset: 0, has_more: false })).toBe(
      false,
    );
  });
  it("normalizes contract, readiness, and validation errors", () => {
    expect(
      normalizeError(422, {
        error: {
          code: "invalid_pagination_window",
          message: "Window exhausted",
        },
      }),
    ).toMatchObject({
      status: 422,
      code: "invalid_pagination_window",
      message: "Window exhausted",
    });
    expect(normalizeError(503, { status: "not_ready" }).code).toBe("not_ready");
    expect(normalizeError(404, {}).message).toContain("not found");
  });
});
