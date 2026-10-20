# ArXiv Explorer: offline corpus and indexes

This repository includes the deterministic 50,000-paper offline pipeline, a FastAPI search backend, and the Phase 4 Next.js frontend with TF-IDF, BM25, semantic and hybrid RRF retrieval. The backend reuses the verified corpus, indexes and model assets read-only. Judged relevance evaluation remains for Phase 5; the frontend provides honest empty evaluation charts and methodology.

## Phase 4 frontend

In a repository-root PowerShell terminal, start the existing backend:

```powershell
.\.venv\Scripts\python.exe -m backend.api
```

In a second terminal:

```powershell
Set-Location frontend
npm ci
Copy-Item .env.example .env.local
npm run dev
```

Open [ArXiv Explorer](http://localhost:3000). The frontend defaults to the backend at `http://127.0.0.1:8000`; configure `NEXT_PUBLIC_API_BASE_URL` in `frontend/.env.local` if needed. Existing indexes are ready: **do not rebuild them**.

The frontend includes shareable filtered search, native ranking scores/explanations, safe legacy-ID paper details, independent recommendations, an algorithm comparison laboratory, light/dark themes, and responsive navigation. All eight existing endpoints are connected. Evaluation displays no fabricated quality metrics.

Validation from `frontend/`:

```powershell
npm run typecheck
npm run lint
npm test
npm run build
npx --no-install playwright install chromium
npm run test:e2e
npm run test:live
```

Use Node 22.19 or newer supported by pinned packages. Live tests require FastAPI to be running. For production locally use `npm run build` then `npm start`. See [frontend architecture](docs/FRONTEND_ARCHITECTURE.md), [API integration](docs/FRONTEND_API_INTEGRATION.md), [setup and testing](docs/FRONTEND_TESTING.md), and [Phase 4 delivery evidence](docs/PHASE4_REPORT.md), including the local CA setup and development-tooling dependency limitations.

## Reproduce on Windows PowerShell

The verified corpus and indexes already exist. **For the search backend, use the backend commands below; do not rerun the offline preparation/build commands.** The offline commands in this section describe the prior phase and should only be used with separate output directories for future experiments.

Use Python 3.12. Dependencies are pinned in `requirements.lock.txt`, including transitive dependencies. Run from the repository root. The existing `.venv` is ready on this machine; skip its creation. For a fresh setup, first ensure `python --version` reports 3.12 before creating the environment.

```powershell
python -m venv .venv
if (Test-Path .bootstrap-certs.pem) {
    $env:SSL_CERT_FILE = (Resolve-Path .bootstrap-certs.pem).Path
    $env:PIP_CERT = $env:SSL_CERT_FILE
}
$env:HF_HUB_DISABLE_XET = '1'
.venv/Scripts/python.exe -m pip install -r requirements.lock.txt
.venv/Scripts/python.exe -m backend.pipeline.download_model --revision 1110a243fdf4706b3f48f1d95db1a4f5529b4d41
.venv/Scripts/python.exe -m backend.pipeline.dataset --size 50000 --seed 42
.venv/Scripts/python.exe -m backend.pipeline.indexes --batch-size 32 --threads 4 --cpu-optimized
.venv/Scripts/python.exe -m backend.pipeline.verify --expected-size 50000
.venv/Scripts/python.exe -m pytest backend/tests -q
.venv/Scripts/python.exe -m backend.pipeline.search "quantum field theory" --algorithm bm25
```

The model-download command needs network access; preparation, building, validation and searching use local files only. On this machine the bundled Python 3.12 runtime was used because the system Python is 3.10. Corporate certificate environments should configure `SSL_CERT_FILE`/pip's `--cert` with their trusted CA bundle; TLS verification stays enabled.

Preparation and index building refuse to overwrite an existing corpus/index directory. To reproduce alongside existing artifacts, use new output paths:

```powershell
.venv/Scripts/python.exe -m backend.pipeline.dataset --output data/processed-repeat --size 50000 --seed 42
.venv/Scripts/python.exe -m backend.pipeline.indexes --corpus data/processed-repeat --output data/indexes-repeat
.venv/Scripts/python.exe -m backend.pipeline.verify --corpus data/processed-repeat --indexes data/indexes-repeat --expected-size 50000
```

For development, `--size 100`, `1000` or `10000` is supported. The same source snapshot, seed and configuration yield identical selected IDs and corpus JSONL bytes. Timing/memory measurements in manifests change between runs. Model/BLAS/package/hardware changes may slightly change floating-point results; package pins, model revision and artifact checksums record provenance.

## Data preparation

The raw file is streamed in binary mode, one record at a time. A temporary SQLite catalogue stores unique IDs, file offsets, broad subject/year strata and SHA256 priorities. Its page cache is bounded to 32 MiB. The full source checksum is computed during that pass. A disk index orders candidates within each stratum; only the chosen records are then sought and loaded. Working memory scales with the requested sample plus fixed catalogue buffers, not the multi-million-record source. The temporary catalogue is removed after success.

Valid papers require an ArXiv ID, nonempty title, abstract, authors, categories and a valid original submission date from the first parsable `versions[].created`. Invalid update dates become null. The first valid occurrence of a duplicate ID wins. Raw display titles/abstracts are retained. Source row/rejection counts and a full source SHA256 appear in `data/processed/manifest.json`.

Strata combine the first listed category's broad subject (`physics`, `math`, `cs`, `stat`, `q-bio`, `q-fin`, `econ`, `eess`, or `other`) with five-year bands. Hamilton largest-remainder allocation assigns proportional integer quotas. It preserves the source distribution without over-weighting tiny strata, so very small strata can receive zero papers. Multi-category papers belong to one sampling stratum but retain every category in metadata. Within each stratum, the smallest SHA256(seed + NUL + ID) values win, with ID tie-breaking. This avoids depending on PRNG state or input order for unique records. Proportional sampling is representative rather than equal-size balancing; major strata retain their observed prevalence. Original and selected counts/fractions are recorded for every stratum.

Selected documents are sorted by ArXiv ID. `doc_ids.json` is the single mapping used by JSONL, SQLite, sparse matrix rows and FAISS positions. SQLite stores all normalized metadata as JSON plus indexed category/date columns; `doc_index` is the contiguous matrix position.

## Indexing and search

Historical category codes are assigned to their modern broad subjects: `cmp-lg` to computer science and `alg-geom`, `dg-ga`, `funct-an`, `q-alg` to mathematics. The current snapshot's final sample has eight represented broad subjects; the fallback `other` stratum has zero selections.

The optional `--cpu-optimized` flag replaces only the transformer encoder with a full-precision OpenVINO graph converted from the local official weights. Sentence Transformers continues to perform tokenization, truncation, pooling and normalization. Weights and inference stay float32; this is not a quantized model. Derived encoder files are checksummed. Validation re-encodes sampled documents with the original PyTorch model, and parity tests cover short and truncated long text. Omit the flag to use PyTorch throughout. See [OpenVINO model conversion](https://docs.openvino.ai/2026/openvino-workflow/model-preparation/conversion-parameters.html).

For an interrupted build, stop the encoder before using `backend.pipeline.checkpoint --corpus ... --indexes ... --model ...`. It validates and seals the completed embedding prefix. A fresh build can use `--reuse-from ...`; reuse requires matching model/artifact fingerprints, paper IDs and semantic text. Reuse is optional and the ordinary commands reproduce the corpus and indexes from scratch.

TF-IDF and BM25 share a vocabulary/tokenizer: Unicode NFKC, conservative LaTeX cleanup, lowercasing, scikit-learn English stopwords and NLTK Porter stemming. Scientific tokens such as C++, GPT-4, L2 and x^2 survive tokenization. `--no-stemming` and `--no-stopwords` support experiments. Title and abstract receive equal weight.

TF-IDF uses smoothed IDF, sublinear TF and unit-normalized float32 CSR rows. Its fitted count vectorizer and TF-IDF transformer are persisted. BM25 uses int32 CSC postings, document lengths and `log(1 + (N-df+0.5)/(df+0.5))` IDF. Defaults are k1=1.5, b=0.75; repeated query terms are counted once. Lexical score ties follow ascending row/ID order. Queries reuse the fitted preprocessing and vocabulary. A query creates only a dense N-element score vector, never a dense corpus-term matrix.

Semantic text keeps natural language and uses `Title: ... Abstract: ...` without stemming or stopword removal. The official `sentence-transformers/all-MiniLM-L6-v2` produces 384-dimensional float32 vectors in bounded batches. The model truncates the combined text at its configured 256 wordpiece-token limit; a vector need not include the complete abstract. Vectors are saved through a NumPy memory map, normalized and added to exact FAISS `IndexFlatIP`. Normalized inner product equals cosine similarity. See [Sentence Transformers encode](https://www.sbert.net/docs/package_reference/sentence_transformer/model.html) and [FAISS cosine guidance](https://github.com/facebookresearch/faiss/wiki/MetricType-and-distances).

`data/indexes/manifest.json` links to the corpus checksum, mapping checksum, model revision/file hashes, package versions and preprocessing parameters. `validation.json` records the actual verification results and real query examples. Checks include all artifact hashes, every SQLite row, every lexical row re-tokenized/reweighted, BM25 statistics, every FAISS vector reconstructed against saved embeddings, normalization, boundary/interior document re-encoding and real searches for all algorithms. These checks establish artifact consistency and smoke retrieval; they do not measure relevance quality without human judgments. Joblib artifacts should only be loaded from trusted local builds.

Large source files, sampled data, model assets and indexes are ignored by Git. Run logs contain structured progress and measured peak resident memory. See [run report](docs/RUN_REPORT.md) for this snapshot's measured results.

## Search backend

The existing `.venv` and application metadata cache are ready. From the repository root:

```powershell
.venv/Scripts/python.exe -m backend.api
```

This uses `.env` or typed defaults: localhost port 8000, one process, two request workers, two computation threads, no query access logs, and a bounded request pool. [Swagger UI](http://127.0.0.1:8000/docs) and [OpenAPI](http://127.0.0.1:8000/openapi.json) are available while the server runs. Ctrl+C performs graceful shutdown. An equivalent explicit command is:

```powershell
.venv/Scripts/python.exe -m uvicorn backend.api.main:app --host 127.0.0.1 --port 8000 --workers 1 --limit-concurrency 32 --no-access-log
```

For a fresh environment, install `requirements.lock.txt` using the earlier certificate configuration and copy `.env.example` to `.env` if custom settings are needed. Relative asset paths are resolved against the repository root. If the separate application cache is absent, create it once:

```powershell
.venv/Scripts/python.exe -m backend.api.prepare_metadata
```

That command streams the original snapshot into `var/metadata.sqlite` for ordered authors and indexed multi-category/year/subject filters. It verifies the source fingerprint and normalized selected records, refuses existing output, and cannot write inside protected corpus/index/model directories. Ordinary requests open both databases read-only. Missing or incompatible resources cause readiness/search HTTP 503 with a clear reason; the process remains live for diagnostics. Startup performs lightweight compatibility checks, never reindexing or downloading a model.

Example PowerShell requests (while the API runs):

```powershell
$base = 'http://127.0.0.1:8000/api/v1'
Invoke-RestMethod "$base/search?q=quantum%20field%20theory&mode=tfidf"
Invoke-RestMethod "$base/search?q=quantum%20field%20theory&mode=bm25"
Invoke-RestMethod "$base/search?q=galaxy%20formation&mode=semantic"
Invoke-RestMethod "$base/search?q=graph%20neural%20networks&mode=hybrid"
Invoke-RestMethod "$base/search?q=graph%20neural%20networks&category=cs.LG&year_from=2020&year_to=2025"
$comparison = @{ query='graph neural networks'; top_k=10; modes=@('tfidf','bm25','semantic','hybrid'); filters=@{category='cs.LG'} } | ConvertTo-Json
Invoke-RestMethod "$base/compare" -Method Post -ContentType 'application/json' -Body $comparison
Invoke-RestMethod "$base/papers?arxiv_id=2410.17617"
Invoke-RestMethod "$base/papers/similar?arxiv_id=2410.17617&limit=5"
Invoke-RestMethod "$base/categories"
Invoke-RestMethod "$base/system/stats"
Invoke-RestMethod "$base/health/ready"
```

Validation commands:

```powershell
.venv/Scripts/python.exe -m pytest backend/tests/api -q
.venv/Scripts/python.exe -m pytest backend/tests/test_pipeline.py -q
.venv/Scripts/python.exe -m backend.api.smoke
.venv/Scripts/python.exe -m backend.api.integrity
```

The smoke command starts a temporary localhost listener, performs real HTTP searches/comparison/filters/recommendations, saves an evidence report under `docs/`, and shuts down cleanly. The integrity command rehashes all protected data/model/index files against the recorded pre-implementation baseline without changing them. The existing root index verifier writes its report, so do not run it against the protected assets during this phase.

[Backend architecture](docs/BACKEND_ARCHITECTURE.md), [API contract](docs/API.md), [retrieval behavior](docs/RETRIEVAL.md), and [Phase 2 & 3 implementation report](docs/PHASE2_REPORT.md) describe the implementation and actual test results. The API returns ordered authors when the official `authors_parsed` field is usable; 2,302 papers retain `authors_text` with `authors_source=raw_only` and an empty structured author list. Frontends should display that fallback. Category readable names are null because authoritative names were not stored in the source corpus.

## Phase 5: evaluation workspace

The evaluation software uses a separate `var/evaluation.sqlite` database. Protected corpus/index/model files and `var/metadata.sqlite` stay unchanged. No relevance judgments are generated automatically. The default collection contains 30 proposed scientific information needs; review them before calling the query set finalized.

Start the backend on localhost with explicit local mutation enablement:

```powershell
$env:EVALUATION_MUTATIONS_ENABLED='true'
.venv/Scripts/python.exe -m backend.api
```

In another PowerShell terminal, start the existing frontend:

```powershell
Set-Location frontend
npm run dev
```

1. Open [evaluation workspace](http://127.0.0.1:3000/evaluation). Review the information needs in **Read query definitions** or **Review / edit / add queries**. Import by pasting JSON; add stable IDs to extend the collection. Saving creates an immutable query-set version.
2. Generate a depth-10 pool for the selected version and common search filters. Depth 20 supports extended assessment. All four algorithms contribute. Repeating the same request returns the existing pool. The initial validated real pool already exists with **622 unique query-paper pairs** across all 30 queries.
3. Follow **Open blind annotation workspace** to [judge papers](http://127.0.0.1:3000/evaluation/judge). Select a query, assess title/abstract, choose 0/1/2 or leave unjudged, then Save. Grades persist; keyboard controls, editing/clearing, progress, resume, navigation, pool search, and CSV export are available.
4. Check readiness. Initially **0 judged / 622 unjudged**; **622 judgments are required** for the full default top-10 comparison. Incomplete queries never receive fabricated metrics. Changing the query set or configuration creates a new pool and changes the workload.
5. Run evaluation after sufficient coverage. It evaluates the same complete queries across methods using frozen rankings and a saved judgment snapshot. For all 30 queries to enter the main comparison, judge all required pairs. Pooled recall is explicitly different from exhaustive corpus recall.
6. Start a benchmark independently. Defaults: 2 warmup rounds, 10 measured rounds per query/method. Inspect progress, failures, mean/P50/P95/min/max/stddev and actual environment metadata. Avoid other heavy workloads while measuring.
7. Select a saved run, compare methods, inspect per-query values/curves and export JSON/CSV/Markdown. Download chart SVGs where offered. A methodology/status report is available before human judgments; it contains no effectiveness conclusions.

Writes default to disabled, require a localhost client, reject untrusted Origins, and are always refused in production. Set `EVALUATION_ENABLED=false` to disable the module. `EVALUATION_DB_PATH` must be separate from protected assets and metadata storage. Use one backend process; public remote annotation and distributed job coordination are outside this phase. Back up the separate evaluation database as described in the architecture document.

PowerShell API workflow:

```powershell
$base='http://127.0.0.1:8000/api/v1/evaluation'
$queries=Invoke-RestMethod "$base/queries"
$body=@{query_set_version=$queries.version; depth=10; random_seed=42; filters=@{}} | ConvertTo-Json
$pool=Invoke-RestMethod "$base/pools" -Method Post -ContentType 'application/json' -Body $body
Invoke-RestMethod "$base/pools/$($pool.id)"
Invoke-RestMethod "$base/progress?pool_id=$($pool.id)"
# After human annotation and required coverage:
$runBody=@{pool_id=$pool.id; cutoff=10; relevance_threshold=1} | ConvertTo-Json
$run=Invoke-RestMethod "$base/runs" -Method Post -ContentType 'application/json' -Body $runBody
Invoke-WebRequest "$base/export?kind=run&id=$($run.id)&format=json" -OutFile 'var/evaluation-run.json'
Invoke-WebRequest "$base/export?kind=report&id=$($run.id)&format=md" -OutFile 'var/evaluation-report.md'
```

Validation commands (from repository root; use a fresh basetemp name on Windows):

```powershell
.venv/Scripts/python.exe -m pytest backend/tests -q -p no:cacheprovider --basetemp var/phase5-tests-local
.venv/Scripts/python.exe -m backend.evaluation.smoke --benchmark --iterations 3
Set-Location frontend
npm run typecheck
npm run lint
npm run test
npm run build
npm run test:e2e
npm run test:evaluation:live
```

The real smoke command creates only unlabeled candidate pools and benchmark samples. The live browser evaluation suite starts an isolated deterministic test corpus/database on ports 8001/3002; predefined test grades never enter `var/evaluation.sqlite`. The ordinary E2E suite uses mocked fixture responses. See [evaluation architecture](docs/EVALUATION_ARCHITECTURE.md), [methodology](docs/EVALUATION_METHODOLOGY.md), [annotation guide](docs/ANNOTATION_GUIDE.md), [API](docs/EVALUATION_API.md), and [benchmarking](docs/BENCHMARKING.md). Software completion does not mean the academic evaluation has been completed.
