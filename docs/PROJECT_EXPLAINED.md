# ArXiv Explorer: beginner study and presentation guide

Audit date: 20 October 2026. This guide compares the local implementation with the supplied Project 18 requirements image. It is an explanation and audit, not a claim that human relevance evaluation has been completed.

## 1. What we built

ArXiv Explorer is a local academic search website over 50,000 sampled arXiv papers. Users type a research topic, select a ranking method, optionally apply metadata filters, and get ranked papers with abstracts, authors, categories, dates, and external arXiv/PDF links.

It has four search modes: TF-IDF, BM25, Semantic, and Hybrid RRF. It also has paper recommendations, a method comparison page, and a research evaluation workspace.

The project searches titles and abstracts. It does not index the full body of every PDF. It retrieves existing papers; it does not generate an answer like a chatbot. A preprint may not have undergone peer review.

Suggested opening: “Our project is an academic paper search engine that compares keyword-based, meaning-based, and hybrid retrieval over a reproducible collection of 50,000 arXiv papers.”

## 2. Requirements audit

| Supplied requirement | Implementation | Assessment |
|---|---|---|
| Academic search for preprints, abstracts and metadata | Search website, metadata, paper pages, external links | Implemented |
| ArXiv corpus described as 1.7M+ records | Local snapshot has 3,205,432 source lines; 50,000 valid unique papers are selected for search | Corpus source used, but full-corpus indexing is not done; confirm subset acceptability with the evaluator |
| Math/LaTeX cleaning | Conservative text cleanup in `backend/pipeline/text.py` | Implemented, not symbolic mathematics understanding |
| Tokenization | Shared scientific-token-aware lexical tokenizer | Implemented |
| Stemming | NLTK Porter stemming for lexical retrieval | Implemented |
| Scientific abstract indexing | Title + abstract TF-IDF/BM25 and semantic representations | Implemented |
| TF-IDF | Saved sparse TF-IDF matrix and fitted query transformation | Implemented |
| BM25 | Saved postings and corpus statistics | Implemented |
| Sentence Transformer | Local all-MiniLM-L6-v2 model, 384-dimensional vectors | Implemented |
| Hybrid RRF | Combines the three base rankers by reciprocal ranks | Implemented |
| Search interface | Next.js/React frontend | Implemented |
| Performance comparison table | Comparison UI and saved repeated latency benchmark | Timing complete; effectiveness table needs judgments |
| Precision@10, Recall, MAP, nDCG | Metric code, evaluation API, saved-run tables and exports | Software implemented; real results pending |
| Precision–recall graph | Per-query/aggregate chart generation from judged runs | Software implemented; real curves pending |

Verified directly in the local databases: 50,000 papers; one query-set version containing 30 queries; one pool containing 622 query–paper pairs; zero relevance judgments; zero effectiveness runs. Therefore, saying “all requirements and experiments are finished” would be inaccurate.

The screenshot names the dataset but does not explicitly authorize a particular sample size. Present the 50,000-paper scope clearly. If full-corpus indexing is mandatory, that remains additional work.

## 3. The three parts of the application

Think of a library:

* Frontend = the counter where the reader enters a request and sees books.
* Backend = the librarian who validates the request, searches, and prepares results.
* Data and indexes = the collection and its catalogues.

The frontend uses TypeScript, React and Next.js. Python powers the data pipeline, retrieval backend and evaluation. SQLite stores structured records. NumPy/SciPy store numerical representations. FAISS searches semantic vectors.

An API is an agreed way for programs to communicate. The browser sends an HTTP request; FastAPI returns JSON, a structured text format containing fields such as title, score and authors. Uvicorn is the server process hosting FastAPI.

## 4. Two flows: preparation and searching

Preparation happens before normal use:

```text
Raw arXiv JSONL snapshot
  -> validate metadata and remove duplicates
  -> select reproducible subject/year sample
  -> save 50,000 papers and shared paper-ID mapping
  -> prepare lexical text and semantic text separately
  -> build TF-IDF, BM25 and semantic/FAISS indexes
  -> verify and save artifacts
```

Normal searching:

```text
User enters topic + method + filters
  -> browser sends API request
  -> backend validates input and finds eligible papers
  -> transforms query using the existing vocabulary/model
  -> scores eligible papers with the requested method
  -> fuses ranks if Hybrid is selected
  -> retrieves metadata for the result page
  -> returns JSON
  -> website displays ranked results
```

Indexes and model are loaded at backend startup. We do not read and process the full raw snapshot on every query. Document embeddings are already saved; semantic search computes a new embedding for the user's query. The model is pretrained; we did not train or fine-tune it on this corpus.

## 5. Dataset preparation

JSONL means one JSON record per line. Each paper contains an ID, title, abstract, author information, categories, version dates, and sometimes DOI/journal details.

The source has 3,205,432 lines. The recorded preparation rejected 31 records with invalid original dates and 92 duplicate IDs, leaving 3,205,309 unique valid records. From these, 50,000 were selected.

The source is about 5.61 GB, so the pipeline streams it one record at a time and uses a temporary disk-backed SQLite catalogue. It avoids loading all papers into a Python list at once.

Sampling groups records by broad subject and five-year submission bands. Proportional quotas preserve the source distribution. Seed 42 and ID-based SHA256 priorities make the selection reproducible. This is not equal numbers per subject: physics contributes more papers because it is more common in the source.

| Subject | Selected papers |
|---|---:|
| Physics | 24,129 |
| Computer science | 13,017 |
| Mathematics | 9,555 |
| Electrical engineering/systems | 1,301 |
| Statistics | 1,030 |
| Quantitative biology | 550 |
| Quantitative finance | 215 |
| Economics | 203 |

`doc_ids.json` ensures that row 123 in a matrix, position 123 in FAISS, and the corresponding database record all refer to the same paper. Without a shared mapping, correct numerical scores could accidentally display the wrong paper.

## 6. Text preprocessing

Lexical methods need comparable word forms:

1. Normalize Unicode characters with NFKC.
2. Conservatively clean LaTeX formatting.
3. Lowercase.
4. Tokenize: split into searchable units.
5. Remove common English stopwords.
6. Apply Porter stemming to reduce related forms to a common stem.

For example, “The networks are learning” becomes searchable content resembling `network`, `learn` after stopword removal and stemming. Stems need not be valid dictionary words.

The tokenizer preserves patterns such as `c++`, `gpt-4`, `l2`, and `x^2`. LaTeX cleanup removes formatting syntax; it does not solve equations or guarantee equivalent mathematical expressions receive the same representation.

The original title and abstract remain available for display. We do not show the stemmed text as the abstract.

Semantic input uses cleaned natural-language text in the form `Title: ... Abstract: ...`, without lexical stemming or stopword removal. Sentence Transformers uses its own wordpiece tokenizer, which is different from the lexical tokenizer.

## 7. The four retrieval methods

### TF-IDF: distinctive shared words

TF means term frequency: how often a word occurs in a document. IDF means inverse document frequency: words found in fewer papers provide more distinguishing evidence.

“Graph” may be useful for a graph query; a common word contributes less. Papers and the query become vectors of word weights, then similarity ranks papers.

The implementation uses smoothed IDF, sublinear TF and unit-normalized sparse vectors. The matrix has 50,000 rows and 129,591 vocabulary columns. A sparse matrix stores nonzero entries rather than allocating a number for every paper–word combination. Titles and abstracts have equal weight.

Strength: simple, explainable lexical baseline. Limitation: different wording can hide a useful match.

### BM25: keyword scoring with saturation and length adjustment

BM25 also matches words, but repeated occurrences have diminishing returns. It adjusts for document length so a long abstract is not rewarded merely for having more words.

```text
score(document, query) = sum over matching unique query terms:
  IDF(term) × f × (k1 + 1)
  / [f + k1 × (1 - b + b × document_length / average_length)]
```

Here `f` is the word count in a paper, `k1=1.5` controls saturation, and `b=0.75` controls length normalization. Corpus-wide statistics remain fixed when filters are applied.

Strength: strong, efficient lexical baseline. Limitation: still depends on vocabulary overlap.

### Semantic search: similarity of learned representations

The pretrained `sentence-transformers/all-MiniLM-L6-v2` model converts text into 384 numerical coordinates called an embedding. Similar research descriptions can receive similar vectors despite different words.

Illustration: “detecting unusual network activity” may relate to “network anomaly detection.” This describes the intended behavior; it is not a guaranteed result for every query.

Vectors are normalized. Their dot product then equals cosine similarity. FAISS `IndexFlatIP` performs exact similarity search over the stored vectors. Filtered search computes exact inner products over eligible saved vectors.

The configured input limit is 256 wordpiece tokens for combined title and abstract. Long abstracts are truncated. Semantic similarity is an approximation of usefulness, not a relevance probability.

Document encoding used a validated full-precision OpenVINO encoder optimization; online query encoding uses the local original PyTorch model. OpenVINO accelerated inference without quantizing weights. This is an implementation optimization, not a different search algorithm.

### Hybrid RRF: agreement between rankings

Hybrid runs TF-IDF, BM25 and Semantic. It combines ranking positions rather than adding their incompatible native scores.

```text
RRF(paper) = sum of 1 / (60 + rank_in_method)
```

Ranks start at 1. A paper missing from a method's candidate list contributes zero for that method. Each method contributes its first 200 candidates. Ties use deterministic paper-ID ordering.

Illustration: Paper A has ranks 1, 3 and 5. Its fused score is `1/61 + 1/63 + 1/65`, approximately 0.04765. Paper B appearing only at semantic rank 1 receives approximately 0.01639. Repeated high placement can therefore outweigh one isolated high placement.

Strength: combines complementary evidence without native-score calibration. Limitation: costs more computation and is not guaranteed to outperform every base method.

## 8. Filters, explanations and recommendations

Filters include category, broad subject, year range and author. Eligibility is applied before selecting the final top results, so the engine searches within the selected subset instead of simply removing nonmatching papers from a global top ten.

Lexical explanations show matched indexed tokens; semantic explanations expose cosine similarity; hybrid explanations expose contributing method ranks/scores and RRF contributions. Scores from different methods are not directly comparable and are not percentages of correctness.

Similar-paper recommendations reuse the selected paper's stored vector, search nearby papers, and exclude the source paper. They are content similarity recommendations, not personalized suggestions learned from user history.

Pagination is bounded: default native ranking windows reach 1,000 and hybrid reaches 200; a request page has at most 100 results. These are retrieval windows, not corpus-size limits.

## 9. Code map and reading order

| File or folder | Purpose |
|---|---|
| `backend/pipeline/dataset.py` | Validation, sampling and corpus creation |
| `backend/pipeline/text.py` | Shared cleaning/tokenization/stemming |
| `backend/pipeline/indexes.py` | Build/load indexes and offline scoring |
| `backend/pipeline/download_model.py` | Obtain pinned model assets for initial setup |
| `backend/pipeline/cpu_model.py` | Optional CPU encoder optimization |
| `backend/pipeline/checkpoint.py` | Validate reusable embedding work |
| `backend/pipeline/verify.py` | Check artifact consistency and mappings |
| `backend/pipeline/search.py` | Command-line search |
| `backend/api/__main__.py` | Starts the API server |
| `backend/api/main.py` | App startup, routes and errors |
| `backend/api/config.py` | Paths, ports, limits and settings |
| `backend/api/schemas.py` | Valid input/output structures |
| `backend/api/resources.py` | Load and check local search assets |
| `backend/api/repository.py` | Metadata lookup and filter eligibility |
| `backend/api/services.py` | Coordinate the full search/compare/recommend flow |
| `backend/api/retrieval/` | TF-IDF/BM25, semantic and RRF retrieval |
| `backend/evaluation/queries.py` | Thirty proposed evaluation information needs |
| `backend/evaluation/metrics.py` | Metric formulas and latency summaries |
| `backend/evaluation/store.py` | Separate evaluation database schema |
| `backend/evaluation/service.py` | Pools, grades, runs and benchmark orchestration |
| `backend/evaluation/router.py` | Evaluation API routes |
| `frontend/app/` | Website routes and page entry points |
| `frontend/components/search/` | Search form, filters and results |
| `frontend/components/papers/` | Paper details and cards |
| `frontend/components/comparison/` | Method comparison screen |
| `frontend/components/evaluation/` | Evaluation dashboard, annotation and charts |
| `frontend/lib/api/` | Typed backend communication |
| `frontend/hooks/queries.ts` | Fetching/caching server responses |
| `backend/tests/`, `frontend/tests/`, `frontend/e2e/` | Automated checks |

Read `text.py`, `schemas.py`, `main.py`, `services.py`, the retrieval modules, and `metrics.py` first. Follow one search before trying to understand the entire repository.

## 10. Python concepts you need

* A **variable** names a value: `cutoff = 10`.
* A **list** stores an ordered collection: `['tfidf', 'bm25']`.
* A **dictionary** maps keys to values: `{'title': 'Example', 'score': 0.8}`.
* A **function** packages a task: `clean(text)` returns cleaned text.
* A **class** groups related data and behavior. `SearchService` coordinates searches; a `Settings` object contains configuration.
* An **import** makes code from another module available.
* A **type hint**, such as `text: str` or `list[str]`, documents expected types. Pydantic adds actual request validation.
* A **loop** repeats an operation over papers, terms, queries or results.
* An **exception** represents failure, such as a missing paper or unavailable index.
* `with` manages a resource and ensures cleanup, for example closing a database connection.
* A **decorator**, such as `@application.get(...)`, registers the function below it as an API route.
* `async`/`await` lets the API wait for work without blocking every other request. CPU-heavy work is dispatched to a bounded thread pool.
* A **virtual environment**, `.venv`, keeps this project's Python packages together.
* `python -m backend.api` runs a package as a program, using `backend/api/__main__.py`.

The search route accepts validated fields, passes them to `SearchService.search`, and returns a structured result. You do not need to explain every asynchronous implementation detail to explain the retrieval method correctly.

## 11. Evaluation: quality versus speed

Search speed asks “How long did retrieval take?” Relevance quality asks “Were the retrieved papers useful for the information need?” A fast system can retrieve poor matches; a slower system can retrieve better ones.

The default set has 30 proposed queries. Each of four methods contributes its top ten papers: up to 1,200 appearances. Deduplication leaves 622 query–paper pairs. The same paper can require separate judgments for different queries.

Human assessors read the information need and paper and assign:

* 0: not relevant.
* 1: partial/indirect relevance.
* 2: substantial direct relevance.
* Unjudged: unknown; it does not mean 0.

The blind annotation view hides the contributing method, original rank and score to reduce bias. Grade 1 or 2 counts as relevant by default; threshold 2 is optional.

| Metric | Meaning |
|---|---|
| Precision@10 | Relevant papers among the first ten, divided by ten |
| Pooled Recall@10 | Relevant retrieved papers divided by known relevant papers in the assessed pool |
| AP@10 | Rewards placing relevant papers earlier; implementation divides relevant-prefix precision sum by `min(R,10)` |
| MAP@10 | Mean AP@10 over the shared eligible queries with defined AP |
| nDCG@10 | Rewards high relevance grades near the top, normalized against the ideal graded ranking |

`R` is the number of known relevant pooled papers. Recall is not exhaustive recall over all 50,000 documents. Zero denominators can produce unavailable metrics rather than made-up zeros.

Example only: if six of the top ten papers are relevant, P@10 = 0.6. If the judged pool contains twelve relevant papers total, pooled Recall@10 = 6/12 = 0.5. These are teaching numbers, not project results.

Precision–recall charts show prefix precision and pooled recall as more ranked results are considered. Actual curves require judgments. The software excludes incomplete queries consistently across all four methods. To include all 30 default queries in the complete top-10 comparison, assess all 622 required pairs. A smaller shared complete query set can support a clearly disclosed preliminary run, not a claim that all 30 were evaluated.

Next steps: review the query definitions; retain the existing pool if unchanged, or generate a new pool for changed definitions; assess and save grades; check readiness; run evaluation at K=10; export results and charts. No labels were invented during this explanatory audit.

## 12. Measured speed results

The completed saved benchmark used 30 queries, four methods, two warmup rounds and ten measured rounds. That is 1,440 executions, including 1,200 measured samples and zero failures. The stored final-run means were checked against SQLite during this audit.

| Method | Mean ms | P50 ms | P95 ms |
|---|---:|---:|---:|
| TF-IDF | 72.02 | 67.83 | 102.04 |
| BM25 | 22.81 | 21.31 | 35.71 |
| Semantic | 51.61 | 46.44 | 90.23 |
| Hybrid | 116.06 | 106.74 | 165.92 |

These are the recorded 13 October local-machine results, not a new timing experiment. They measure steady-state `SearchService.search` time, excluding model loading, HTTP transport, queue time and benchmark persistence. P50 is the median; P95 describes the upper tail. BM25 was fastest in this experiment. This provides no evidence that it was most relevant. Hybrid includes three retrieval methods, so its larger cost is understandable.

## 13. Features beyond the minimum brief

* Category/subject/year/author filtering and shareable search URLs.
* Dedicated paper pages and external arXiv/PDF links.
* Similar-paper recommendations using existing embeddings.
* Side-by-side rank comparison, result overlap and rank differences.
* Matched-token, cosine and RRF contribution explanations.
* Responsive desktop/mobile layout and light/dark themes.
* Health/readiness and corpus/model/index statistics.
* Reproducible proportional sampling, shared IDs and SHA256 artifact provenance.
* CPU optimization and validated embedding reuse for offline preparation.
* Blind human annotation, resumable judgments and immutable experiment snapshots.
* Query-set versions, frozen candidate pools, benchmark histories and exports.
* JSON/CSV/Markdown exports and supported chart SVG downloads.
* Automated pipeline/API/frontend/browser tests and documented integrity checks.

## 14. Run on this computer

The existing `.venv`, dependencies, corpus, model, indexes and metadata cache are present. Python is 3.12.14; Node is v22.19.0. There is no need to rebuild indexes or run `npm ci` for each demo.

Open two PowerShell terminals. In terminal 1:

```powershell
Set-Location 'C:\Users\Dev Arora\Documents\ChatGPT\IR Project'
$env:EVALUATION_MUTATIONS_ENABLED='true'
.\.venv\Scripts\python.exe -m backend.api
```

The environment setting enables local evaluation actions such as saving grades, generating pools and starting benchmark/evaluation jobs. Ordinary search does not need it. Set it in the same terminal before starting the backend. Keep this terminal running and wait for startup to finish.

In terminal 2:

```powershell
Set-Location 'C:\Users\Dev Arora\Documents\ChatGPT\IR Project\frontend'
npm run dev
```

Open `http://127.0.0.1:3000` in your browser. The frontend already defaults to the local backend; `frontend/.env.local` is optional for these defaults. Useful pages:

* Home: `http://127.0.0.1:3000`
* Comparison: `http://127.0.0.1:3000/compare`
* Evaluation: `http://127.0.0.1:3000/evaluation`
* Human annotation: `http://127.0.0.1:3000/evaluation/judge` (follow the pool link from Evaluation)
* API documentation: `http://127.0.0.1:8000/docs`
* Search readiness: `http://127.0.0.1:8000/api/v1/health/ready`

Press Ctrl+C in each terminal to stop. Closing a browser tab does not stop the servers. `localhost`/`127.0.0.1` refers to your own computer. Normal search works from local assets; opening an external arXiv paper/PDF requires internet.

Optional command-line search without the website:

```powershell
Set-Location 'C:\Users\Dev Arora\Documents\ChatGPT\IR Project'
.\.venv\Scripts\python.exe -m backend.pipeline.search 'quantum field theory' --algorithm bm25
```

If dependencies are missing on a fresh copy, follow README setup: Python 3.12, pinned Python requirements, supported Node, `npm ci`, and provision the large data/model/index assets. Large assets are ignored by Git, so copying only tracked source is insufficient to reproduce this ready-to-run state. Use fresh output directories for a rebuild experiment.

## 15. Troubleshooting

| Symptom | Check/action |
|---|---|
| Website unavailable | Keep terminal 2 running; read its actual URL/port |
| Website opens but search fails | Check backend terminal and readiness endpoint |
| API 503/not ready | Read backend startup error; check corpus/index/model/metadata paths |
| Port already in use | Identify the existing server; use it if correct, or stop that server before restarting |
| Save/pool/run controls disabled | Start backend with evaluation mutation variable enabled in that terminal; use local development mode |
| Evaluation run rejects incomplete judgments | Finish the required query–paper judgments; this is expected behavior |
| Keyword query has no results | Try simpler words or Semantic; the sampled corpus may not contain the topic |
| Only a few filtered results | Broaden restrictive filters |
| Module/package missing | Use the project's `.venv` Python, not a different system interpreter |
| Missing author list or unfamiliar category codes | Source fallback author text and category codes are supported |

Do not delete `var/evaluation.sqlite`: it contains saved judgments and experiments. Back it up with the server stopped or with SQLite's backup API. Do not rebuild existing data/index directories merely to start the website.

## 16. Suggested presentation: 12 slides

1. **Title and problem.** “Researchers need to find useful literature despite differing terminology.”
2. **Objectives and scope.** Search metadata/abstracts; compare four methods; explain the 50,000-paper sample.
3. **Dataset.** Source size, validation, reproducible proportional sampling, retained fields.
4. **Architecture.** Frontend -> FastAPI -> retrieval indexes + SQLite -> results. Separate offline preparation from online search.
5. **Preprocessing.** A small cleaning/tokenization/stemming example; semantic text follows a separate path.
6. **TF-IDF and BM25.** Distinctive keywords; saturation and length normalization.
7. **Semantic search.** Pretrained model -> 384-dimensional vectors -> cosine/FAISS; acknowledge truncation.
8. **Hybrid RRF.** Show `sum(1/(60+rank))` and one small worked example.
9. **Live demonstration.** Search, switch methods, filter, inspect paper, recommendations, compare.
10. **Evaluation design.** Thirty information needs, pooled candidates, blind grades, metrics and charts.
11. **Verified results.** Show measured latency; disclose zero human judgments and pending real quality results until assessment is completed.
12. **Extras, limitations and future work.** Recommendations/explanations/exports; full-corpus expansion, judged evaluation, improved long-text handling.

Aim for 10–15 minutes depending on your allotted time. Spend most explanation time on the pipeline and differences between methods, not package versions or CSS.

## 17. Demo sequence

1. Start both servers in advance and verify readiness.
2. Open Home and explain the real corpus statistics.
3. Search `graph neural networks` in BM25.
4. Run the same query in Semantic and Hybrid; show changed rankings without claiming the changes prove improvement.
5. Apply `cs.LG` and a year range such as 2020–2025; clear filters afterward.
6. Open a result; show full abstract, metadata and similar papers.
7. Compare all four methods for the same query and filters; explain overlap/rank differences and why native scores cannot be compared directly.
8. Open Evaluation; show the candidate pool and actual judgment status.
9. Explain the 0/1/2 assessment process and existing speed benchmark. Do not fabricate labels just to fill charts.
10. If genuine judgments have been completed before the presentation, show their saved run/table/curves and disclose the query count; otherwise explicitly describe the pending work.

## 18. Likely viva questions

**Why four methods?** They contrast lexical weighting, lexical saturation/length adjustment, semantic representation, and rank fusion.

**Why 50,000 papers?** It is a documented local resource-conscious experimental scope with reproducible sampling. It is not full-corpus indexing, and sampling limits coverage.

**Did you train an AI model?** No. We used a pretrained Sentence Transformer and generated corpus/query embeddings.

**Why not stem semantic text?** The model expects natural-language context; lexical normalization has a different purpose.

**Why RRF rather than adding scores?** The three score scales differ; rank positions provide a shared basis.

**Is Hybrid best?** We cannot establish that without genuine relevance judgments. It combines complementary methods but can still fail.

**Which method is fastest?** BM25 in the saved local steady-state benchmark; this is conditional on that corpus/hardware/configuration.

**Is a cosine score of 0.8 equal to 80% accuracy?** No. It is a similarity score.

**Does Recall measure every relevant paper in the full collection?** No. Current evaluation uses known relevant papers in a candidate pool.

**What is an index?** A prepared representation that avoids starting from raw source text for every query.

**Why SQLite and FAISS?** SQLite stores/filters metadata; FAISS searches numerical semantic vectors. They solve different parts of retrieval.

**Does it fetch new papers on every query?** No. It searches a fixed local snapshot.

**Why are charts empty?** No real judgments or effectiveness runs exist yet; the application deliberately avoids invented results.

**What would you improve?** Complete human evaluation, expand corpus scope if required, investigate better domain/long-text embeddings, and evaluate proposed changes using the same judged queries.

## 19. Evidence and limits

The audit read implementation files, manifests/reports and the live SQLite files in read-only mode for status checks. It confirmed stored final benchmark means. Current frontend verification: 29 tests passed and TypeScript typechecking passed. A fresh full backend pytest run did not finish or produce a summary in this session and was stopped; it is not counted as a new pass or evidence of a code failure.

The previous Phase 5 report records 69 passing backend tests, frontend/build/browser checks, and 46 unchanged protected artifacts. These historical checks should be distinguished from checks rerun during this audit. Fixture screenshots/tests demonstrate UI/software behavior, not genuine research effectiveness.

Some README introduction wording still describes the earlier Phase 4 state; its later Phase 5 section and evaluation modules document the implemented evaluation workspace. Do not interpret that older introduction as absence of the evaluation software.

Useful supporting documents: `README.md`, `docs/RETRIEVAL.md`, `docs/EVALUATION_METHODOLOGY.md`, `docs/ANNOTATION_GUIDE.md`, `docs/BENCHMARKING.md`, `docs/PHASE5_REPORT.md`, and `docs/RUN_REPORT.md`.
