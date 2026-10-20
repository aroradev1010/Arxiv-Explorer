# API contract

Base URL: `http://127.0.0.1:8000/api/v1`. Swagger: `/docs`; schema: `/openapi.json`.

| Method | Path | Parameters / body |
| --- | --- | --- |
| GET | `/search` | `q`, `mode`, `category`, `subject`, `year_from`, `year_to`, `author`, `limit`, `offset` |
| GET | `/papers` | `arxiv_id` (query parameter supports legacy slashes) |
| GET | `/papers/similar` | `arxiv_id`, `limit` (default 5) |
| GET | `/categories` | all indexed category and primary broad-subject counts |
| POST | `/compare` | `{query, top_k, modes, filters}` |
| GET | `/system/stats` | actual corpus/index/model versions, counts, build configuration, current RSS and startup time |
| GET | `/health/live` | process liveness |
| GET | `/health/ready` | loaded compatible engine and accessible metadata |

Search defaults are hybrid mode, limit 10 and offset 0, configurable in `.env`. Queries require at least one alphanumeric character and at most 1,000 characters. Limits are 1–100; offsets nonnegative. Publication years are 1991–2100, inclusive, with from <= to. All filters combine with AND. Unknown category/author combinations return HTTP 200 with no results. Subject is one of physics, math, cs, stat, q-bio, q-fin, econ, eess or other. Filters apply before top-K selection, including secondary-category membership.

Search responses contain the normalized query, selected mode, filters, pagination, ranked complete paper metadata, native scores, ranking details, measured timing stages and the index-manifest SHA256 as `index_version`. Rank is absolute within the bounded ranking window, so page two begins at offset+1. Metadata includes ordered names when available, `authors_text` and `authors_source`; preserve the raw fallback when the structured list is empty. Publication/update dates remain separate. Readable category names are null when not stored in the dataset.

The supported window is 1,000 for each native method and 200 for hybrid by default. Hybrid retrieves the top 200 eligible candidates from each native method, fuses their union, and exposes its top 200. `offset + limit` beyond the configured window produces an explicit 422. `ranked_candidate_count` counts documents within that window; it is not a corpus-wide relevance count. `has_more` means another result exists inside the verified window, and is false at its end even if the corpus could contain more matches.

`ranking_details` contains `final_rank`; lexical modes include matched indexed/stemmed query tokens, semantic mode includes native cosine similarity, and hybrid includes final RRF score and each present ranker's 1-based rank, native score and actual contribution. An absent ranker contributes zero. Scores are not probabilities. No word-level causal explanation of transformer similarity is claimed.

Comparison returns `methods` with each method's search response, pairwise overlapping IDs, per-paper ranks (null when absent from a displayed top-K) and `delta_by_pair = rank(second) - rank(first)`. All methods use the same eligibility. Top-K defaults to 10, modes default to all four and duplicate modes are rejected.

`timing_ms` measures preprocessing, eligibility, embedding, each native retrieval, summed retrieval, fusion, metadata and total. Unused stages are zero. Search total is actual service-entry-to-assembled-response time; transport/queue/serialization overhead is outside it. Comparison top-level total is measured overall time; method totals are attributed sums of actual shared preprocessing/eligibility/metadata and the method's required measured stages, not independently timed repeated requests. Formal benchmarking requires warmup and repeated runs.

Errors consistently use `{error: {code, message, details}}`. Invalid requests/modes/windows return 422; absent papers 404; unavailable assets/metadata or exhausted worker admission 503; unexpected failures 500 with a generic message. Validation details include location/message/type without echoing request values, SQL, paths or stack traces. Liveness stays available after an explicit resource initialization failure; readiness returns 503 and a sanitized diagnostic. Production request logging omits query strings with the recommended launcher.
