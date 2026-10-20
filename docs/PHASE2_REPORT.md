# Phase 2 & 3 implementation report — 13 October 2026

Implemented and verified a FastAPI backend over the existing **50,000-paper** corpus. The dataset, index files, model assets and verified manifests were neither rebuilt nor altered. All **45 protected files** match their pre-implementation SHA256/size records, with no additions/removals and no mismatch against existing corpus/index/source fingerprints.

## Components and architecture

Typed settings and Pydantic v2 contracts; lifespan resource loading; shared ID/position mapping; read-only corpus access; separate indexed application metadata cache; TF-IDF/BM25/semantic adapters; mathematical RRF; shared filter resolution; search/paper/recommendation/comparison services; actual stage timings; sanitized errors; CORS; liveness/readiness and statistics; bounded CPU dispatch with serialized model inference and graceful cleanup. The existing CLI and pipeline code remain unchanged. Existing BM25 scoring and preprocessing are reused.

The separate `var/metadata.sqlite` contains secondary-category relationships, original publication years, broad subjects, Unicode-normalized author lookup text and ordered source author names. Source checksum and normalized records were checked while preparing it. The verified database stores only author display strings, so this extra application-owned cache supplies structured names without migrating the corpus.

## Endpoints

| Method | Endpoint | Behavior |
| --- | --- | --- |
| GET | `/api/v1/search` | q, mode, category, subject, year_from/year_to, author, limit/offset; rankings, metadata, explanations, pagination, timings |
| GET | `/api/v1/papers` | stable arxiv_id query parameter, complete available metadata, unknown ID 404 |
| GET | `/api/v1/papers/similar` | arxiv_id and limit, existing-vector recommendations, source excluded |
| GET | `/api/v1/categories` | actual multi-category and broad-subject counts |
| POST | `/api/v1/compare` | query, top_k, modes and filters; same eligible corpus, overlaps, ranks/deltas, RRF details |
| GET | `/api/v1/system/stats` | actual versions/configuration/counts/model/dimensions/current RSS/startup time |
| GET | `/api/v1/health/live` | process liveness |
| GET | `/api/v1/health/ready` | loaded compatible resources and accessible read-only metadata |

Swagger `/docs` and OpenAPI `/openapi.json` were checked. See [API contract](API.md) and [architecture](BACKEND_ARCHITECTURE.md).

## Genuine outputs

Actual HTTP query: **quantum field theory**, top five requested, first two shown. Scores are native relevance scores, not probabilities or quality judgments.

| Mode | Rank | ArXiv ID | Score | Title |
| --- | ---: | --- | ---: | --- |
| tfidf | 1 | 2411.19601 | 0.472584 | Quantum simulation of thermal field theories |
| tfidf | 2 | 1503.00675 | 0.429648 | The quantum field theory interpretation of quantum mechanics |
| bm25 | 1 | 2411.19601 | 13.316024 | Quantum simulation of thermal field theories |
| bm25 | 2 | 2507.11541 | 12.816489 | Koopman-von Neumann Field Theory |
| semantic | 1 | 1503.00675 | 0.654366 | The quantum field theory interpretation of quantum mechanics |
| semantic | 2 | hep-th/0101174 | 0.652049 | Boundary integrable quantum field theories |
| hybrid | 1 | 1503.00675 | 0.048395 | The quantum field theory interpretation of quantum mechanics |
| hybrid | 2 | 2507.11541 | 0.047875 | Koopman-von Neumann Field Theory |

A real hybrid query for graph neural networks with secondary-category-capable `cs.LG` and original publication years 2020–2025 returned `2410.17617` at rank 1. Its metadata was fetched again and matched exactly. The same run verified a case-normalized author filter, all-mode filtered comparison and recommendations that excluded the source paper. Full responses and contribution values are in `PHASE2_API_SMOKE.json`.

## Validation actually executed

```powershell
.venv/Scripts/python.exe -m pytest backend/tests/api -q
.venv/Scripts/python.exe -m pytest backend/tests/test_pipeline.py -q
.venv/Scripts/python.exe -m backend.api.smoke
.venv/Scripts/python.exe -m backend.api.integrity
.venv/Scripts/python.exe -m pip check
.venv/Scripts/python.exe -m backend.api
```

- Final backend suite: **44 passed in 13.75 seconds**. One dependency deprecation warning, no failures/skips.
- Existing pipeline suite: **9 passed in 15.08 seconds**, no skips. Its new fixture artifacts are temporary, not protected files.
- Real-index test loads the corpus once: four queries × four modes, CLI score/ranking parity, finite/unique/sorted results, exact metadata/ID mapping, actual filters/comparison/recommendations.
- Unit/API cases cover filter-before-top-K for a sole eligible document outside the global top ten in every native method, secondary categories, Unicode/case-folded authors, original rather than update years, unknown dates, combined/empty filters, zero lexical overlap, correct RRF arithmetic/duplicates/ties/depth, bounded pagination, concurrent reads, one shared comparison embedding, invalid inputs and sanitized errors.
- Failure tests cover missing/corrupt assets, read-only metadata availability, explicit 503, forbidden metadata-cache placement and worker-capacity rejection with responsive liveness.
- Live socket run: **16 real search requests**, plus filtered/author searches, details, recommendations, comparison, categories, stats, health and Swagger; **clean shutdown confirmed**.
- Exact launcher was also started on `127.0.0.1:8000`; readiness returned ready and stats returned 50,000. Ctrl+C produced application shutdown complete and finished-server messages.
- `pip check`: no broken requirements. Installed dependencies were pinned in the updated lockfile; original index-library versions are retained and checked at startup.

## Observed timings and memory

One-off actual HTTP requests for quantum field theory, without formal warmup/repetition:

| Mode | Service total (ms) | HTTP round trip (ms) |
| --- | ---: | ---: |
| tfidf | 34.972 | 43.517 |
| bm25 | 6.278 | 11.840 |
| semantic | 23.975 | 30.631 |
| hybrid | 37.616 | 43.554 |

The HTTP smoke process reported current RSS **717.4 MiB**, and startup **8253.156 ms**. These are observed local values, not median/P95 benchmarks. Each response exposes actual preprocessing, eligibility, embedding, individual rankers, fusion, metadata and total stages. Comparison shares measured work; its method totals are attributed stage sums, while its top-level total is measured overall elapsed time.

## Artifact integrity

`PHASE2_ARTIFACT_BASELINE.json` records pre-implementation fingerprints. `PHASE2_ARTIFACT_INTEGRITY.json` reports **passed**, **45 files**, **zero changed/added/removed protected files**, **zero manifest fingerprint mismatches**. This includes raw snapshot, sampled corpus, SQLite, mapping, embeddings, FAISS/sparse/joblib files, original/derived models, and verified manifests/reports. No root index verifier was run because that command would rewrite its validation report.

## Run and next phase

From the repository root, with the existing environment/cache:

```powershell
.venv/Scripts/python.exe -m backend.api
```

Open `http://127.0.0.1:8000/docs`. Configuration is in `.env.example`; paths are repository-root-relative. Default process count is one; request workers two; computation threads two. The application cache already exists. On a fresh setup, install `requirements.lock.txt`, configure trusted certificates if needed, then run `backend.api.prepare_metadata` once. Do not rerun corpus/index generation. [README](../README.md) supplies concrete requests and validation commands.

The API is ready for Next.js integration through explicit development CORS and typed OpenAPI contracts, and for later judged evaluation using genuine native/hybrid rankings. No frontend, relevance judgments, training, PDFs, authentication or fabricated evaluation metrics were introduced.

## Known limits

- 2,302 source records lack usable `authors_parsed` names: the response preserves `authors_text`, labels `authors_source=raw_only`, and returns an empty structured list rather than guessing people. Author filtering still includes their original text.
- Author matching is normalized substring matching, not person-identity disambiguation. Category readable names are null because authoritative names are absent from corpus metadata.
- Ranking windows are bounded: native 1,000, hybrid 200 by default. Requests beyond the window return 422; has_more is limited to that window.
- Corpus embeddings can truncate long abstracts at 256 tokens, unchanged from the verified phase.
- Starlette currently emits a deprecation warning for TestClient's installed HTTPX transport. All tests pass; no production failure was observed.
- Formal latency distributions and relevance quality remain for the evaluation phase.

New source modules are under `backend/api/`, with isolated and real-index tests under `backend/tests/api/`. Documentation adds `BACKEND_ARCHITECTURE.md`, `API.md`, `RETRIEVAL.md` and the evidence/report files. `.env.example`, `.gitignore`, `pytest.ini`, `requirements.lock.txt` and README were added/updated. No changes were made to the existing pipeline implementation or protected data assets.
