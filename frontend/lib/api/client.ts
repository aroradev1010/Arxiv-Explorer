import { z } from "zod";
import { params } from "../state";
import type { SearchState } from "../state";
import type {
  Paper,
  SearchResponse,
  Categories,
  Stats,
  Health,
  SimilarResponse,
  CompareRequest,
  CompareResponse,
} from "./types";
export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}
export function normalizeError(status: number, body: unknown) {
  const b = z
    .object({ error: z.object({ code: z.string(), message: z.string() }) })
    .safeParse(body);
  if (b.success)
    return new ApiError(status, b.data.error.code, b.data.error.message);
  return new ApiError(
    status,
    status === 503 ? "not_ready" : "http_error",
    status === 503
      ? "Search index is not ready. Try again shortly."
      : status === 422
        ? "Check the query, filters, and supported ranking window."
        : status === 404
          ? "Paper not found in the indexed corpus."
          : "The search service returned an unexpected error.",
  );
}
const num = z.number().finite();
const nullable = z.string().nullable();
const mode = z.enum(["tfidf", "bm25", "semantic", "hybrid"]);
export const paperSchema = z.object({
  id: z.string(),
  title: z.string(),
  abstract: z.string(),
  authors: z.array(z.string()),
  authors_text: z.string(),
  authors_source: z.enum(["authors_parsed", "raw_only"]),
  primary_category: z.string(),
  categories: z.array(z.string()),
  published_at: nullable,
  updated_at: nullable,
  doi: nullable.optional(),
  journal_ref: nullable.optional(),
  comments: nullable.optional(),
  license: nullable.optional(),
  arxiv_url: z.string(),
  pdf_url: z.string(),
});
const ranked = z.object({
  paper: paperSchema,
  rank: num,
  score: num,
  algorithm: mode,
  ranking_details: z.object({
    final_rank: num,
    matched_indexed_tokens: z.array(z.string()).nullable().optional(),
    cosine_similarity: num.nullable().optional(),
    rrf_score: num.nullable().optional(),
    contributions: z
      .record(
        z.string(),
        z.object({ rank: num, native_score: num, contribution: num }),
      )
      .nullable()
      .optional(),
  }),
});
const timing = z.object({
  preprocessing: num,
  eligibility: num,
  embedding: num,
  tfidf: num,
  bm25: num,
  semantic: num,
  retrieval: num,
  fusion: num,
  metadata: num,
  total: num,
});
const filters = z.object({
  category: nullable.optional(),
  subject: nullable.optional(),
  author: nullable.optional(),
  year_from: num.nullable().optional(),
  year_to: num.nullable().optional(),
});
const search = z.object({
  query: z.string(),
  mode,
  filters,
  pagination: z.object({
    limit: num,
    offset: num,
    returned: num,
    has_more: z.boolean(),
    ranking_window_size: num,
    ranked_candidate_count: num,
  }),
  results: z.array(ranked),
  timing_ms: timing,
  index_version: z.string(),
});
const category = z.object({
  code: z.string(),
  name: nullable.optional(),
  count: num,
});
const categories = z.object({
  categories: z.array(category),
  subjects: z.array(category),
});
const stats = z.object({
  indexed_paper_count: num,
  algorithms: z.array(mode),
  vocabulary_size: num,
  embedding_dimension: num,
  embedding_model: z.string(),
  model_revision: nullable,
  dataset_version: z.string(),
  index_version: z.string(),
  index_schema_version: num,
  index_build_information: z.record(z.string(), z.unknown()),
  category_counts: categories,
  process_rss_bytes: num,
  startup_ms: num,
  worker_threads: num,
  compute_threads: num,
});
const health = z.object({
  status: z.enum(["live", "ready", "not_ready"]),
  reason: nullable.optional(),
});
const similar = z.object({
  arxiv_id: z.string(),
  results: z.array(ranked),
  timing_ms: timing,
  index_version: z.string(),
});
const compare = z.object({
  query: z.string(),
  filters,
  methods: z.record(z.string(), search),
  overlaps: z.record(z.string(), z.array(z.string())),
  rank_differences: z.array(
    z.object({
      paper_id: z.string(),
      ranks: z.record(z.string(), num.nullable()),
      delta_by_pair: z.record(z.string(), num.nullable()),
    }),
  ),
  timing_ms: timing,
  index_version: z.string(),
});
export async function request<T>(
  path: string,
  schema: z.ZodType,
  signal?: AbortSignal,
  body?: object,
): Promise<T> {
  const controller = new AbortController();
  const abort = () => controller.abort();
  signal?.addEventListener("abort", abort, { once: true });
  if (signal?.aborted) controller.abort();
  const timeout = setTimeout(() => controller.abort("timeout"), 60000);
  try {
    const response = await fetch(
      `${(process.env.NEXT_PUBLIC_API_BASE_URL || "http://127.0.0.1:8000").replace(/\/$/, "")}/api/v1${path}`,
      {
        signal: controller.signal,
        ...(body
          ? {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify(body),
            }
          : {}),
      },
    );
    let data: unknown;
    try {
      data = await response.json();
    } catch {
      throw new ApiError(
        response.status,
        "invalid_response",
        "The service returned an unreadable response.",
      );
    }
    if (!response.ok) throw normalizeError(response.status, data);
    const parsed = schema.safeParse(data);
    if (!parsed.success)
      throw new ApiError(
        0,
        "invalid_response",
        "The service response does not match the API contract.",
      );
    return parsed.data as T;
  } catch (e) {
    if (e instanceof ApiError) throw e;
    if (signal?.aborted) throw e;
    throw new ApiError(
      0,
      controller.signal.aborted ? "timeout" : "network_error",
      controller.signal.aborted
        ? "Search timed out. Try again."
        : "Search service unavailable. Start the backend and try again.",
    );
  } finally {
    clearTimeout(timeout);
    signal?.removeEventListener("abort", abort);
  }
}
export const api = {
  search: (s: SearchState, signal?: AbortSignal, limit = 10) =>
    request<SearchResponse>(
      "/search?" +
        params({ q: s.q, mode: s.mode, ...s.filters, offset: s.offset, limit }),
      search,
      signal,
    ),
  paper: (id: string, signal?: AbortSignal) =>
    request<Paper>("/papers?" + params({ arxiv_id: id }), paperSchema, signal),
  similar: (id: string, signal?: AbortSignal) =>
    request<SimilarResponse>(
      "/papers/similar?" + params({ arxiv_id: id, limit: 5 }),
      similar,
      signal,
    ),
  categories: (signal?: AbortSignal) =>
    request<Categories>("/categories", categories, signal),
  stats: (signal?: AbortSignal) =>
    request<Stats>("/system/stats", stats, signal),
  health: (kind: "live" | "ready", signal?: AbortSignal) =>
    request<Health>("/health/" + kind, health, signal),
  compare: (body: CompareRequest, signal?: AbortSignal) =>
    request<CompareResponse>("/compare", compare, signal, body),
};
