# Phase 5 implementation and validation report

Validated on 13 October 2026 (Asia/Calcutta).

**Milestone 1: evaluation software implemented and validated. Milestone 2: academic effectiveness evaluation remains pending human query review and relevance judgments.** No real effectiveness values or pseudo-human labels have been created.

## 1. Implemented modules

`backend/evaluation/` contains pure metrics, validated requests, typed response contracts, a SQLite schema migration, a proposed query collection, frozen pools, judgment persistence/readiness, immutable runs/snapshots/rankings, bounded background pooling/benchmarks, export/report routes, and a real-corpus smoke CLI. Existing FastAPI lifespan/configuration integrate these services without changing retrieval algorithms.

`frontend/components/evaluation/` and `frontend/lib/api/evaluation.ts` implement the interactive workspace, blind annotation, Zod boundaries, TanStack Query caching/mutations/polling, charts, SVG downloads and exports. `/evaluation` and `/evaluation/judge` are functional. OpenAPI and generated TypeScript include evaluation contracts. Database: `var/evaluation.sqlite`; no full paper metadata duplication.

Architecture, methodology, annotation, API and benchmark documentation are provided in the five EVALUATION/BENCHMARKING/ANNOTATION markdown documents and README.

## 2. Evaluation methodology

All four methods contribute top-10 candidates using the same query definitions, corpus and filters. IDs are deduplicated per query. Query sets and pool configurations are frozen; changes create versions. Deterministic shuffled annotation hides method/rank/score.

Grades 0/1/2 are manually assigned; unjudged stays unknown. Default binary threshold is grade>=1, configurable to 2. Graded nDCG keeps original grades. P@K uses a fixed K denominator even for a short returned list. AP@K divides accumulated relevant-prefix precision by min(known relevant,K). Recall is explicitly pooled/judged-set recall. No known relevant documents makes recall/AP undefined; zero ideal gain makes nDCG undefined. Incomplete top-K union coverage excludes a query across all methods; zero eligible queries rejects execution with HTTP 409. Aggregates use the same eligible queries and disclose defined counts/spread. Curves are measured prefix points; aggregate curves use macro means by rank without interpolation. Historical grade snapshots cannot change when current judgments are edited.

## 3. Query collection

30 proposed, human-reviewable information needs; version `qs-3b3d382cbf222d5dc118a4a0`. Supports JSON import/edit/add/export and up to 200 queries per collection.

Scientific domains: {"computer_science": 6, "cross_disciplinary": 1, "economics": 2, "electrical_engineering": 3, "mathematics": 4, "physics": 5, "quantitative_biology": 3, "quantitative_finance": 2, "statistics": 4}.

Types: {"cross_disciplinary": 1, "exact": 7, "narrow": 6, "natural_language": 5, "technical": 8, "vocabulary_mismatch": 3}.

These queries require user review before academic finalization; they are not relevance evidence.

## 4. Actual candidate pooling

Real pool `pool-5f258767e5624a608c13eba1bfeb2d27` completed over the verified 50,000-paper corpus, depth 10, seed 42, unfiltered. Actual contributing ranking hits: **1200**. Deduplicated query-paper pairs: **622**. Duplicate contributions removed: **578 (48.17%)**. Candidate order/provenance are persisted. The identical request reuses this pool. Extended depth-20 pools are supported but were not generated during validation.

## 5. Actual human judgment progress

**0 judged, 622 unjudged, 0 eligible queries. 622 required judgments remain for all 30 queries to enter the main K=10 comparison.** No production effectiveness runs exist. The real incomplete run request returned HTTP 409 and produced no fabricated metrics.

| Query | Required judgments remaining |
|---|---:|
| Q001 | 21 |
| Q002 | 22 |
| Q003 | 28 |
| Q004 | 19 |
| Q005 | 16 |
| Q006 | 19 |
| Q007 | 20 |
| Q008 | 27 |
| Q009 | 22 |
| Q010 | 21 |
| Q011 | 21 |
| Q012 | 26 |
| Q013 | 26 |
| Q014 | 15 |
| Q015 | 20 |
| Q016 | 24 |
| Q017 | 28 |
| Q018 | 21 |
| Q019 | 20 |
| Q020 | 18 |
| Q021 | 17 |
| Q022 | 18 |
| Q023 | 17 |
| Q024 | 17 |
| Q025 | 22 |
| Q026 | 20 |
| Q027 | 20 |
| Q028 | 22 |
| Q029 | 15 |
| Q030 | 20 |


## 6. Metric verification

Hand-checked ranking A,B,C,D with grades 2,0,1,2, plus another relevant pool paper E(1): P@10=.3, pooled Recall@10=.75, AP@10=(1+2/3+3/4)/4=.6041666667, DCG=4.7920296742, IDCG=5.8234658188, nDCG=0.8228827683. Threshold 2 gives P=.2, recall=1, AP=.75; graded nDCG is unchanged. [1,2,3,4,5] latency samples give mean/P50=3, P95=4.8 and population stddev=sqrt(2).

Tests assert these formulas and values, unknown grades, zero denominators, duplicate rankings, short lists, threshold behavior, deterministic aggregation, transactional rollback, all four pool contributors, uniqueness, frozen versions, blind responses, snapshot persistence, stale/depth rejection, shared-query exclusions, restart failure states, benchmark failures/admission and exports. Fixture grades remain isolated from real data.

## 7. Actual final latency benchmark

ID `bench-d9ead381d213431faea3509f8aef0b5f`; state **COMPLETED**; 30 queries x 4 methods x (2 warmup + 10 measured rounds) = **1440 executions**; **0 failures**. Warmups excluded: 240; measured samples: 1,200 (300 per method). Randomized deterministic sequence; one retrieval job; no test/build workload during this final measurement. Normal OS background activity cannot be eliminated or fully measured.

| Method | Measured N | Mean ms | P50 ms | P95 ms | Min ms | Max ms | Stddev ms |
|---|---:|---:|---:|---:|---:|---:|---:|
| tfidf | 300 | 72.02 | 67.83 | 102.04 | 56.25 | 327.00 | 19.49 |
| bm25 | 300 | 22.81 | 21.31 | 35.71 | 14.39 | 61.36 | 7.07 |
| semantic | 300 | 51.61 | 46.44 | 90.23 | 35.79 | 289.81 | 21.06 |
| hybrid | 300 | 116.06 | 106.74 | 165.92 | 85.41 | 396.23 | 33.63 |


Environment: `{"compute_threads": 2, "corpus_size": 50000, "cpu": "Intel64 Family 6 Model 140 Stepping 1, GenuineIntel", "embedding_model": "sentence-transformers/all-MiniLM-L6-v2", "logical_cpu_count": 8, "os": "Windows-11-10.0.26200-SP0", "python": "3.12.14", "worker_threads": 2}`.

Scope: full steady-state SearchService.search wall time, excluding model loading, HTTP round trip, job queue and sample persistence. P95 uses linear interpolation at (N-1)*.95. Earlier exploratory measurements are stored separately; the table uses only the final default-size run. Raw stage timings, timestamps, warmups, environment and configurations are in `PHASE5_LIVE_SMOKE.json` and the evaluation database/export API. Speed does not establish effectiveness superiority.

## 8. Frontend interactions and visual QA

Query-set/version selection and JSON review/import/edit; shared-filter/depth pool creation and job state; exact judgment workload/readiness; blind annotation with query information need, title/authors/categories/year/full abstract/ArXiv link; 0/1/2 and unjudged controls; save/edit/clear/error handling; keyboard shortcuts ignored while typing; auto next-unjudged, previous/next/jump, search and pagination; draft/navigation/reload protection; persisted progress/grade distributions.

Saved run selection, metric cards, common-query comparison table, per-query metrics/curves, frozen ranking/score/grade analysis, historical staleness, benchmark status/P50/P95/mean/spread/environment, CSV/JSON/Markdown downloads and chart SVG exports. Honest unavailable states remain when no evidence exists. Browser Back cancellation is included in the unsaved-grade browser scenarios.

Desktop annotation and mobile dashboard screenshots were visually inspected and remained within viewport width. Saved screenshots under `docs/screenshots/phase5-fixture-*` contain explicitly synthetic evaluation fixtures, not genuine production results. Existing responsive/dark-theme tokens and navigation are reused.

## 9. Exact validation commands and observed results

```powershell
.venv/Scripts/python.exe -m pytest backend/tests -q -p no:cacheprovider --basetemp var/phase5-complete-final
# 69 passed; includes real-index regressions and 16 evaluation tests.
Set-Location frontend
npm run typecheck
# Passed.
npm run lint
# Passed, no warnings.
npm run test
# 29 passed across 4 files.
npm run build
# Passed; all original routes plus /evaluation/judge generated.
npm run test:e2e
# 22 unchanged desktop/mobile browser regressions passed.
# Early evaluation runs exposed a DOM reference bug and a browser Back draft-guard issue; both were corrected and the affected scenarios rerun.
npm run test:e2e -- --grep 'annotation persists|unsaved annotations'
# Final affected-suite rerun: 4 passed (desktop/mobile).
npm run test:evaluation:live
# 2 passed against isolated real HTTP FastAPI fixture storage (desktop/mobile).
Set-Location ..
.venv/Scripts/python.exe -m backend.evaluation.smoke --benchmark --iterations 10
# Real 30-query pool reused; 622 unlabeled pairs; 409 incomplete run;
# final benchmark completed 1440 executions with zero errors.
```

All 26 ordinary browser scenarios were covered by the 22 passing unchanged regressions and four passing final affected-scenario checks; the full combined command was not repeated after the scoped fix. Two additional real-backend browser cases passed. Initial Windows sandbox temporary-directory/subprocess restrictions were resolved by running the authorized checks with normal Windows access. The harmless existing Starlette httpx deprecation warning remains; no test or implementation blocker remains.

## 10. Artifact integrity

SHA-256 baseline captured before implementation for all protected raw/corpus/index/model files and the separate metadata cache. Rehash after implementation and final benchmark: **46 protected files unchanged**, zero added/removed/changed files. Evidence: `PHASE5_ARTIFACT_BASELINE.json`, `PHASE5_ARTIFACT_INTEGRITY.json`. Existing index manifests and verification reports were not regenerated. No dataset preparation or corpus embedding generation was performed.

## 11. Limitations

Academic relevance evaluation is unfinished because no real human judgments or finalized query review exist. Pooling is incomplete relative to the entire corpus. Extended-pool unknowns can change recall/IDCG when later judged. No inter-assessor agreement or significance testing is claimed. Local single-process annotation only; production/remote writes are refused. HTTP round-trip benchmark mode and dedicated cold-start benchmark are not implemented. Graceful shutdown waits for accepted jobs; forceful cancellation is not exposed. Annotation resume chooses the first unjudged candidate on the current 100-item page; larger pools have explicit pagination. CSV input import is not implemented; JSON import and CSV/JSON export are available.

## 12. Exact next user actions

From repository root in PowerShell:

```powershell
$env:EVALUATION_MUTATIONS_ENABLED='true'
.venv/Scripts/python.exe -m backend.api
```

In another terminal:

```powershell
Set-Location frontend
npm run dev
```

Open http://127.0.0.1:3000/evaluation. Review query definitions; save another version and generate a new pool if changed. Otherwise select existing pool `pool-5f258767e5624a608c13eba1bfeb2d27`. Open the blind annotation link (route `/evaluation/judge`), assess the **622 required pairs** and save grades. Return to evaluation; require all 30 queries ready for the full comparison, then Run evaluation at K=10/threshold1. Start a separate latency benchmark when desired; inspect measured timing units/status. Select run history, view method/per-query curves and tables, and download CSV/JSON/Markdown/SVG. Export methodology/status before effectiveness is available. Back up `var/evaluation.sqlite` after stopping the server or using SQLite backup.
