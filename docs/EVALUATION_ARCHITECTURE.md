# Evaluation architecture

Phase 5 adds `backend/evaluation` without rebuilding retrieval. `EvaluationService` uses the existing loaded `SearchService.rankings` for four-method pools and `SearchService.search` for independent benchmarks. Corpus, indexes, model, mappings, and metadata cache stay read-only. Application state lives in `var/evaluation.sqlite`.

## Pipeline and versions

The 30 proposed information needs in `queries.py` cover eight ArXiv scientific domains plus a cross-disciplinary climate topic. Query types are exact, natural language, vocabulary mismatch, technical, narrow, and cross-disciplinary. IDs are stable. Saving a validated query array creates a content-addressed query-set version; previous definitions remain accessible. Import JSON through the editor; append further IDs to expand to 50 or more.

A pool freezes query definitions, filters, depth, seed, corpus fingerprint, index fingerprint, and the actual RRF/ranking-window/index-manifest configuration. The request content hash makes retries idempotent. A changed configuration creates another pool. A failed pool can be retried; partial documents are removed on failure. Each query-paper pair is deduplicated; per-method ranks and native scores are retained in provenance. Sorted candidate IDs are shuffled using a deterministic query-specific seeded generator. Annotation responses omit provenance entirely.

`run` reconstructs ranked lists from frozen pool provenance; it never reruns retrieval. A single SQL join captures the judgment snapshot. Runs preserve grades, snapshot fingerprint, ranked IDs/scores, configuration, metric definitions, exclusions, per-query metrics, and aggregates. Editing or clearing a judgment cannot change a prior run. Asset/configuration mismatch marks saved pools and results stale. An old query version remains usable as an explicitly selected frozen experiment; it is never silently rewritten to the latest query text.

## Persistence and migration

The `Store` creates schema version 1 under `PRAGMA user_version`; unknown schema versions fail rather than silently migrating. Tables: query_sets, evaluation_queries, candidate_pools, pool_documents, relevance_judgments, evaluation_runs, evaluation_rankings, evaluation_metrics, benchmark_runs, benchmark_samples. Composite primary keys prevent duplicate query-paper judgments and ranking positions. Foreign keys enforce pool membership and run ownership. A pool/query/order index supports deterministic annotation pagination. Transactions commit on success, roll back on errors, and each connection is closed promptly. No paper abstracts are copied into evaluation storage.

On startup, interrupted QUEUED/RUNNING jobs are marked FAILED. A pool that was interrupted can be retried using its original request. One-process deployment is required: process-local admission controls are not a multi-process distributed lock. A single executor and nonblocking admission lock allow at most one retrieval-intensive pool or benchmark job. There is no unbounded job queue. CPU work stays off the FastAPI event loop. Graceful shutdown waits for accepted retrieval jobs before closing search resources. Metric calculations are short in-memory snapshot operations dispatched to a worker thread.

Evaluation initialization errors are logged without disabling existing search endpoints. Disabled evaluation returns 503. Missing search resources still allow query/status inspection, but retrieval-dependent operations return an explicit error.

## API and UI integration

Routes are installed under `/api/v1/evaluation`. Pydantic request and response contracts are included in `frontend/lib/api/openapi.json`; `generated.ts` is regenerated with openapi-typescript. The client validates responses with Zod, uses the shared request/error/timeout handling, and uses TanStack Query for caching, mutation invalidation, and active-job polling. `/evaluation` manages the workflow; `/evaluation/judge` uses blind metadata and persisted progress.

## Configuration

`EVALUATION_ENABLED=true`, `EVALUATION_DB_PATH=var/evaluation.sqlite`, `EVALUATION_MUTATIONS_ENABLED=false`. All three settings are enforced. Writes require explicit enablement, a localhost client, a trusted Origin when supplied, and a non-production environment. There are no frontend secrets or new accounts. Never publicly proxy this accountless local annotation backend. Production remains read-only even if the mutation setting is enabled.

Depth, seed, filters, selected queries/version, K, relevance threshold, warmup count and measured count are validated request parameters and saved in experiment metadata. Defaults are pool depth 10, seed 42, K=10, threshold=1, warmup 2, measured rounds 10. Depth 20 supports extended pools; depth and K are bounded at 100 and also by existing retrieval limits. Full top-K union coverage is mandatory and cannot be bypassed by configuration.

## Backup

Stop the single backend process before copying `var/evaluation.sqlite`, or use Python's SQLite backup API while running. Preserve this database with the protected artifact fingerprints and exports. Restore only into the separate evaluation path. Do not copy or alter the verified corpus database to back up judgments.

```powershell
Copy-Item -LiteralPath 'var/evaluation.sqlite' -Destination 'var/evaluation-backup.sqlite'
```

Exports sort rows and keys deterministically. CSV user text starting with spreadsheet formula characters is escaped. JSON exports preserve the actual text and experiment metadata. Keep independent backup files; do not overwrite the only judgment database.
