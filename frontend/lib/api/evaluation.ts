import { z } from "zod";
import { request, paperSchema } from "./client";
import type { components } from "./generated";

export const querySchema = z.object({
  id: z.string(),
  query: z.string(),
  information_need: z.string(),
  domain: z.string(),
  query_type: z.string(),
  notes: z.string(),
});
const collectionSchema = z.object({
  version: z.string(),
  queries: z.array(querySchema),
  versions: z.array(z.object({ version: z.string(), created_at: z.string() })),
});
const identity = {
  corpus_version: z.string(),
  index_fingerprint: z.string(),
  algorithm_configuration: z.record(z.unknown()),
  queries: z.array(querySchema),
  query_set_version: z.string(),
};
const poolSchema = z.object({
  id: z.string(),
  status: z.string(),
  error: z.string().nullable(),
  candidate_count: z.number(),
  stale: z.boolean(),
  metadata: z.object({
    ...identity,
    depth: z.number(),
    random_seed: z.number(),
    filters: z.record(z.unknown()),
  }),
});
const progressQuery = z.object({
  query_id: z.string(),
  total: z.number(),
  judged: z.number(),
  unjudged: z.number(),
  required: z.number(),
  missing_required: z.number(),
  status: z.string(),
  percent: z.number(),
  known_relevant: z.number(),
  grades: z.record(z.number()),
});
const progressSchema = z.object({
  pool_id: z.string(),
  total: z.number(),
  judged: z.number(),
  unjudged: z.number(),
  required: z.number(),
  missing_required: z.number(),
  eligible_queries: z.number(),
  queries: z.array(progressQuery),
});
const documentSchema = z.object({
  query_id: z.string(),
  paper_id: z.string(),
  relevance_grade: z.number().nullable(),
  annotation_order: z.number(),
  paper: paperSchema,
});
const documentsSchema = z.object({
  total: z.number(),
  offset: z.number(),
  items: z.array(documentSchema),
});
const value = z.number().finite().nullable();
const aggregates = z
  .object({
    precision: value,
    pooled_recall: value,
    ap: value,
    ndcg: value,
    query_count: z.number(),
  })
  .passthrough();
const pointSchema = z.object({
  rank: z.number(),
  precision: z.number(),
  pooled_recall: value,
});
const metricSchema = z.object({
  query_id: z.string(),
  algorithm: z.string(),
  precision: value,
  pooled_recall: value,
  ap: value,
  dcg: value,
  ndcg: value,
  coverage: z.number(),
  status: z.string(),
  curves: z.array(pointSchema),
});
const runSchema = z.object({
  id: z.string(),
  pool_id: z.string(),
  status: z.string(),
  stale: z.boolean(),
  created_at: z.string(),
  metadata: z.object({
    ...identity,
    cutoff: z.number(),
    relevance_threshold: z.number(),
    eligible_queries: z.array(z.string()),
    excluded_queries: z.array(
      z.object({ query_id: z.string(), status: z.string() }),
    ),
    aggregate: z.record(aggregates),
  }),
  metrics: z.array(metricSchema).nullable().optional(),
  rankings: z
    .array(
      z.object({
        query_id: z.string(),
        algorithm: z.string(),
        rank: z.number(),
        paper_id: z.string(),
        native_score: z.number(),
      }),
    )
    .nullable()
    .optional(),
  judgment_snapshot: z
    .record(z.record(z.number().nullable()))
    .nullable()
    .optional(),
});
const summary = z.object({
  count: z.number(),
  mean: value,
  p50: value,
  p95: value,
  minimum: value,
  maximum: value,
  stddev: value,
});
const benchmarkSchema = z.object({
  id: z.string(),
  status: z.string(),
  error: z.string().nullable(),
  completed_samples: z.number(),
  failed_samples: z.number(),
  metadata: z
    .object({
      total_samples: z.number(),
      timing_scope: z.string(),
      environment: z.record(z.unknown()),
    })
    .passthrough(),
  summary: z.record(summary),
});
const curvesSchema = z.object({
  points: z.array(
    pointSchema.extend({ query_id: z.string(), algorithm: z.string() }),
  ),
  aggregate: z.array(
    pointSchema.extend({ algorithm: z.string(), query_count: z.number() }),
  ),
  convention: z.string(),
});

function get<S extends z.ZodTypeAny>(
  path: string,
  schema: S,
  signal?: AbortSignal,
) {
  return request<z.infer<S>>("/evaluation" + path, schema, signal);
}
function send<S extends z.ZodTypeAny>(
  path: string,
  schema: S,
  body: object,
  method = "POST",
) {
  return request<z.infer<S>>(
    "/evaluation" + path,
    schema,
    undefined,
    body,
    method,
  );
}
export const evaluationApi = {
  config: (signal?: AbortSignal) =>
    get(
      "/config",
      z.object({ enabled: z.boolean(), mutations_enabled: z.boolean() }),
      signal,
    ),
  queries: (signal?: AbortSignal, version?: string) =>
    get(
      "/queries" + (version ? "?version=" + encodeURIComponent(version) : ""),
      collectionSchema,
      signal,
    ),
  saveQueries: (queries: EvaluationQuery[]) =>
    send("/queries", collectionSchema, { queries }),
  pools: (signal?: AbortSignal) => get("/pools", z.array(poolSchema), signal),
  createPool: (body: object) => send("/pools", poolSchema, body),
  progress: (id: string, signal?: AbortSignal, cutoff = 10, threshold = 1) =>
    get(
      `/progress?pool_id=${encodeURIComponent(id)}&cutoff=${cutoff}&threshold=${threshold}`,
      progressSchema,
      signal,
    ),
  documents: (
    id: string,
    q: string,
    offset = 0,
    text = "",
    signal?: AbortSignal,
  ) =>
    get(
      `/pools/${encodeURIComponent(id)}/judgments?query_id=${encodeURIComponent(q)}&offset=${offset}&limit=100&text=${encodeURIComponent(text)}`,
      documentsSchema,
      signal,
    ),
  judge: (id: string, q: string, p: string, grade: number | null) =>
    send(
      `/pools/${encodeURIComponent(id)}/judgments`,
      z.object({
        saved: z.literal(true),
        query_id: z.string(),
        paper_id: z.string(),
        relevance_grade: z.number().nullable(),
      }),
      { query_id: q, paper_id: p, relevance_grade: grade },
      "PUT",
    ),
  runs: (signal?: AbortSignal) => get("/runs", z.array(runSchema), signal),
  run: (id: string, signal?: AbortSignal) =>
    get("/runs/" + encodeURIComponent(id), runSchema, signal),
  createRun: (body: object) => send("/runs", runSchema, body),
  curves: (id: string, signal?: AbortSignal) =>
    get(`/runs/${encodeURIComponent(id)}/curves`, curvesSchema, signal),
  benchmarks: (signal?: AbortSignal) =>
    get("/benchmarks", z.array(benchmarkSchema), signal),
  createBenchmark: (body: object) => send("/benchmarks", benchmarkSchema, body),
  exportUrl: (kind: string, id?: string, format = "json") =>
    `${(process.env.NEXT_PUBLIC_API_BASE_URL || "http://127.0.0.1:8000").replace(/\/$/, "")}/api/v1/evaluation/export?kind=${kind}&format=${format}${id ? "&id=" + encodeURIComponent(id) : ""}`,
};
export type EvaluationQuery = components["schemas"]["EvaluationQuery"];
export type EvaluationRunContract = components["schemas"]["RunResponse"];
export type EvaluationPoolContract = components["schemas"]["PoolResponse"];
export type Pool = z.infer<typeof poolSchema>;
export type JudgmentDocument = z.infer<typeof documentSchema>;
export type Metric = z.infer<typeof metricSchema>;
