// Synthetic evaluation fixtures only; never saved to the production evaluation database.
import paper from "./fixtures/paper.json" with { type: "json" };
import type { JudgmentDocument } from "@/lib/api/evaluation";
export const evaluationQuery = {
  id: "Q001",
  query: "quantum fixture",
  information_need: "Find quantum research in this synthetic test collection.",
  domain: "physics",
  query_type: "exact",
  notes: "Automated fixture only",
};
export const collection = {
  version: "qs-fixture",
  queries: [evaluationQuery],
  versions: [{ version: "qs-fixture", created_at: "2026-01-01" }],
};
export const poolFixture = {
  id: "pool-fixture",
  status: "COMPLETED",
  error: null,
  candidate_count: 2,
  stale: false,
  metadata: {
    corpus_version: "fixture",
    index_fingerprint: "fixture",
    algorithm_configuration: {},
    query_set_version: "qs-fixture",
    queries: [evaluationQuery],
    depth: 10,
    random_seed: 42,
    filters: {},
  },
};
export const documentFixture: JudgmentDocument = {
  query_id: "Q001",
  paper_id: paper.id,
  relevance_grade: null,
  annotation_order: 0,
  paper: {
    ...paper,
    authors_source: "authors_parsed",
    title: "Synthetic evaluation paper A",
  },
};
export const secondDocument = {
  ...documentFixture,
  paper_id: "2001.00001",
  annotation_order: 1,
  paper: { ...paper, id: "2001.00001", title: "Synthetic evaluation paper B" },
};
export const progressFixture = {
  pool_id: "pool-fixture",
  total: 2,
  judged: 0,
  unjudged: 2,
  required: 2,
  missing_required: 2,
  eligible_queries: 0,
  queries: [
    {
      query_id: "Q001",
      total: 2,
      judged: 0,
      unjudged: 2,
      required: 2,
      missing_required: 2,
      status: "INCOMPLETE",
      percent: 0,
      known_relevant: 0,
      grades: { "0": 0, "1": 0, "2": 0 },
    },
  ],
};
const modes = ["tfidf", "bm25", "semantic", "hybrid"];
export const runFixture = {
  id: "run-fixture",
  pool_id: "pool-fixture",
  status: "COMPLETED",
  stale: false,
  created_at: "2026-01-01",
  metadata: {
    ...poolFixture.metadata,
    cutoff: 10,
    relevance_threshold: 1,
    eligible_queries: ["Q001"],
    excluded_queries: [],
    aggregate: Object.fromEntries(
      modes.map((m) => [
        m,
        { precision: 0.1, pooled_recall: 1, ap: 1, ndcg: 1, query_count: 1 },
      ]),
    ),
  },
  metrics: modes.map((algorithm) => ({
    query_id: "Q001",
    algorithm,
    precision: 0.1,
    pooled_recall: 1,
    ap: 1,
    dcg: 3,
    ndcg: 1,
    coverage: 1,
    status: "READY",
    curves: [
      { rank: 1, precision: 1, pooled_recall: 1 },
      { rank: 2, precision: 0.5, pooled_recall: 1 },
    ],
  })),
};
export const benchmarkFixture = {
  id: "bench-fixture",
  status: "COMPLETED",
  error: null,
  completed_samples: 4,
  failed_samples: 0,
  metadata: {
    total_samples: 4,
    timing_scope: "Synthetic service-level timing fixture",
    environment: { os: "Test fixture" },
  },
  summary: Object.fromEntries(
    modes.map((m) => [
      m,
      { count: 1, mean: 3, p50: 3, p95: 3, minimum: 3, maximum: 3, stddev: 0 },
    ]),
  ),
};
