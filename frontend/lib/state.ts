import { z } from "zod";
import type {
  Filters,
  Mode,
  Paper,
  SearchResponse,
  RankedPaper,
} from "./api/types";
export const modes: Mode[] = ["hybrid", "tfidf", "bm25", "semantic"];
export const labels: Record<Mode, string> = {
  hybrid: "Hybrid",
  tfidf: "TF-IDF",
  bm25: "BM25",
  semantic: "Semantic",
};
export const descriptions: Record<Mode, string> = {
  hybrid: "Reciprocal Rank Fusion",
  tfidf: "Term-weighted keyword matching",
  bm25: "Probabilistic keyword ranking",
  semantic: "Meaning-based vector retrieval",
};
export const querySchema = z
  .string()
  .trim()
  .min(1, "Enter a research topic.")
  .max(1000, "Use 1,000 characters or fewer.")
  .refine(
    (v) => /[\p{L}\p{N}]/u.test(v),
    "Include at least one letter or number.",
  );
const year = z.coerce.number().int().min(1991).max(2100);
export const filterSchema = z
  .object({
    category: z.string().trim().max(80).optional(),
    subject: z
      .enum([
        "physics",
        "math",
        "cs",
        "stat",
        "q-bio",
        "q-fin",
        "econ",
        "eess",
        "other",
      ])
      .optional(),
    author: z.string().trim().max(200).optional(),
    year_from: year.optional(),
    year_to: year.optional(),
  })
  .refine(
    (v) =>
      v.year_from === undefined ||
      v.year_to === undefined ||
      v.year_from <= v.year_to,
    { message: "From year must not exceed To year.", path: ["year_to"] },
  );
export interface SearchState {
  q: string;
  mode: Mode;
  offset: number;
  filters: Filters;
}
export function parseState(p: Pick<URLSearchParams, "get">): SearchState {
  const raw: Record<string, string | number> = {};
  for (const key of ["category", "subject", "author", "year_from", "year_to"]) {
    const v = p.get(key);
    if (v) raw[key] = key.startsWith("year_") ? Number(v) : v;
  }
  const mode = p.get("mode");
  const offset = Number(p.get("offset") || 0);
  return {
    q: p.get("q") || "",
    mode: modes.includes(mode as Mode) ? (mode as Mode) : "hybrid",
    offset: Number.isInteger(offset) && offset >= 0 ? offset : 0,
    filters: raw as Filters,
  };
}
export function params(values: object): URLSearchParams {
  const p = new URLSearchParams();
  for (const [k, v] of Object.entries(values))
    if (v !== undefined && v !== null && v !== "") p.set(k, String(v));
  return p;
}
export function searchURL(s: SearchState) {
  return (
    "/search?" +
    params({ q: s.q, mode: s.mode, ...s.filters, offset: s.offset })
  );
}
export function paperURL(id: string) {
  return "/papers?" + params({ arxiv_id: id });
}
export const validID = (id: string) =>
  /^(?:\d{4}\.\d{4,5}|[a-z][a-z.-]*(?:\.[A-Z]{2})?\/\d{7})$/.test(id);
export function documentURL(id: string, pdf = false) {
  return validID(id) ? `https://arxiv.org/${pdf ? "pdf" : "abs"}/${id}` : null;
}
export function authors(p: Paper) {
  return p.authors.length
    ? p.authors.join(", ")
    : p.authors_text || "Author metadata unavailable";
}
export function dateLabel(v: string | null) {
  if (!v) return null;
  const d = new Date(v);
  return Number.isNaN(d.getTime()) ||
    !/^\d{4}-\d{2}-\d{2}$/.test(v) ||
    d.toISOString().slice(0, 10) !== v
    ? null
    : d.toLocaleDateString("en-GB", {
        day: "numeric",
        month: "short",
        year: "numeric",
        timeZone: "UTC",
      });
}
export function scoreLabel(mode: Mode) {
  return {
    hybrid: "RRF score",
    tfidf: "TF-IDF score",
    bm25: "BM25 score",
    semantic: "Cosine similarity",
  }[mode];
}
export function score(v: number, mode: Mode) {
  return v.toFixed(mode === "hybrid" ? 6 : 4);
}
export function canNext(p: SearchResponse["pagination"]) {
  return p.has_more && p.offset + p.limit < p.ranking_window_size;
}
export function nextLimit(p: SearchResponse["pagination"]) {
  return Math.min(p.limit, p.ranking_window_size - p.offset - p.limit);
}
export function fusionSummary(r: RankedPaper) {
  const c = Object.values(r.ranking_details.contributions || {});
  const sum = c.reduce((n, v) => n + v.contribution, 0);
  const constants = c.map((v) => 1 / v.contribution - v.rank);
  const k =
    constants.length &&
    constants.every((v) => Math.abs(v - constants[0]) < 1e-6)
      ? Math.round(constants[0])
      : null;
  return { sum, k, matches: Math.abs(sum - r.score) < 1e-8 };
}
