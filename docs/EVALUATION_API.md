# Evaluation API

Prefix `/api/v1/evaluation`. Swagger and generated OpenAPI provide typed request/response schemas. Errors use the existing `error: {code,message,details}` envelope. Disabled evaluation returns 503; local write protection returns 403; incompatible/incomplete experiments or occupied retrieval job capacity return 409; invalid inputs return 422; unknown objects return 404.

| Method | Path | Request / response |
|---|---|---|
| GET | /config | enabled, mutations_enabled |
| GET | /queries?version=... | version, queries, versions |
| POST | /queries | `{queries:[{id,query,information_need,domain,query_type,notes}]}`; save immutable content-addressed collection |
| PATCH | /queries/{query_id} | complete query definition, stable same ID; creates new collection version |
| GET | /pools | saved pool metadata/status/candidate count/staleness |
| POST | /pools | optional query_set_version, query_ids, depth(1..100), random_seed, filters; 202 job, idempotent by frozen configuration |
| GET | /pools/{pool_id} | job state, metadata, error, candidate_count, stale |
| GET | /pools/{pool_id}/judgments | required query_id; offset>=0, limit 1..100, status all/judged/unjudged, text; blind metadata and grade, deterministic order |
| PUT | /pools/{pool_id}/judgments | `{query_id,paper_id,relevance_grade:0|1|2|null}`; saved=true only after transaction commit |
| GET | /progress | pool_id, cutoff(default10), threshold(default1); total/judged/unjudged, eligible_queries, missing_required and per-query grade distribution/status |
| POST | /runs | pool_id, cutoff, relevance_threshold; 201 immutable snapshot results, same eligible queries across methods; 409 if none eligible |
| GET | /runs | history, metadata, aggregates, staleness |
| GET | /runs/{run_id} | metadata, judgments snapshot, metrics, frozen rankings |
| GET | /runs/{run_id}/metrics | aggregate, per_query, excluded_queries, stale |
| GET | /runs/{run_id}/queries | frozen query definitions, metrics, rankings |
| GET | /runs/{run_id}/curves | per-query points, macro means by rank, aggregation convention |
| POST | /benchmarks | pool-request query selection/filter/depth/seed fields plus warmup_iterations(0..10), measured_iterations(1..30); 202 |
| GET | /benchmarks | job history, environment/configuration, samples, summaries |
| GET | /benchmarks/{id} | persisted status/progress/failures, samples, summary |
| GET | /export | kind, id, format=json/csv/md; Content-Disposition download |

Default query_ids means all queries in the selected/latest version. Duplicate query IDs/text and unknown selected IDs are rejected. Query import supports up to 200 queries. Query text/information needs are preserved; normalized text is used only for duplicate detection.

Exports: `queries` accepts an optional query-set version as id; `pool` and `judgments` use pool id; `run`, `metrics`, `aggregate`, `curves` use run id; `benchmark` uses benchmark id. JSON preserves metadata/results; CSV projects sorted rows. `report` uses run id and Markdown for an empirical research summary; omitted id or a pool id creates a methodology/status report without inventing results. SVG charts are downloadable in the dashboard. CSV and JSON curve exports preserve measured points for other plotting tools.

Metrics use cutoff-neutral keys precision, pooled_recall, ap, dcg, ndcg with K stored in metadata. For K=10 the dashboard labels P@10, Pooled Recall@10, MAP@10, nDCG@10. Unavailable values are null, never fabricated zeros. Per-metric aggregation counts and standard deviations distinguish exclusions.

Pool states QUEUED/RUNNING/COMPLETED/FAILED are distinct from query readiness INCOMPLETE/READY/STALE/INSUFFICIENT_DEPTH/NOT_STARTED. Benchmarks additionally expose COMPLETED_WITH_ERRORS. Historical query definitions remain frozen; changing the active/latest query set does not rewrite old experiments.

PowerShell examples and startup instructions are in README. Keep the server single-process and local. Mutations require `EVALUATION_MUTATIONS_ENABLED=true` and are refused in APP_ENV=production. No authentication mechanism for public remote annotation is implemented.
