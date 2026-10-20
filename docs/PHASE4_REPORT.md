# Phase 4 delivery report

Verified on 13 October 2026, Windows PowerShell, Node 22.19 and the existing Python virtual environment.

## Implemented frontend

`frontend/` is a complete Next.js App Router application connected to the existing FastAPI service. It provides functional TF-IDF, BM25, semantic and hybrid search; combined filters; URL restoration/history; bounded pagination; metadata/details; similar papers; native ranking explanations; a comparison laboratory; current dataset statistics/health; and an evaluation foundation without invented metrics.

Routes: `/`, `/search`, `/papers?arxiv_id=...`, `/compare`, `/evaluation`, `/about`, and an application not-found page. Details preserve legacy identifiers with slashes in query parameters. Search cards support full abstract expansion, author fallback, categories, publication dates and trusted arXiv/PDF links. Recommendation errors do not disable metadata. Comparison exposes shared eligibility, top-K, per-method rankings, overlaps, returned ranks/deltas, contribution sums and genuine request timings.

## Architecture and integration

Server page/layout components wrap interactive client features. TypeScript contracts are generated from captured runtime OpenAPI and checked at the fetch boundary with Zod. TanStack Query manages cached server state, complete query keys, request deduplication and cancellation; URL parameters own applied research state; React Hook Form validates search drafts. Theme preferences persist with next-themes. shadcn-style Button and Radix Sheet primitives, Tailwind semantic tokens and Lucide provide a restrained academic interface.

All eight existing endpoints are connected and tested: search, papers, similar papers, categories, comparison, system statistics, liveness and readiness. Existing backend CORS supports the local frontend; no backend contract or retrieval logic changes were required.

Live corpus evidence: **50,000 indexed papers, 174 categories, four algorithms and 384 semantic dimensions**. Read-only smoke results are saved in [PHASE4_LIVE_SMOKE.json](PHASE4_LIVE_SMOKE.json). Hybrid's first paper for “graph neural networks” is `2410.17617` with score `0.048651507139079855`; BM25's first paper is `1804.01487` with score `16.180229421405368`; semantic's first paper is `1905.03046` with similarity `0.6352552771568298`. These are native values, not probabilities or cross-method normalized scores. Exact fetched metadata was compared to the search response. Five recommendations excluded their source. A combined category/subject/year/author query returned the expected source paper. Actual legacy ID `acc-phys/9411004` was fetched successfully. Comparison contributions agreed with fused scores.

## User experience

Verified desktop, tablet and mobile widths include 360, 390, 768, 1024 and 1280 pixels. Search filters open in a focus-managed mobile drawer. Comparison switches visible method on mobile and scrolls tables within their containers. Theme persistence, navigation, Back/Forward, filter reset/restoration, abstract expansion, disabled/loading states and recoverable errors are tested. Page errors were absent in the live desktop flow. Paper text renders as escaped React content, with original LaTeX preserved as text.

## Executed validation

| Command | Actual result |
| --- | --- |
| `npm run typecheck` | Passed strict TypeScript |
| `npm run lint` | Passed, no errors or warnings |
| `npm run build` | Passed; all six application routes and not-found prerendered successfully |
| `npm test` | 22 passed across unit, API boundary and component suites |
| `npm run test:e2e` | 22 passed across desktop/mobile Chromium; also passed against the production build |
| `npm run test:live` | Two real-backend desktop/mobile flows passed against the final production server (5.8 seconds overall) |
| `.\.venv\Scripts\python.exe frontend/scripts/live-smoke.py` | Passed all four modes, combined filters, legacy metadata, details, similar papers and comparison |
| `.\.venv\Scripts\python.exe frontend/scripts/integrity.py` | Passed, 45 protected files unchanged and metadata SHA256 unchanged |
| `npm audit --omit=dev` | Zero reported production vulnerabilities |

Fixture browser tests use clearly marked real-API snapshots and synthetic edge cases. Live tests call the real backend with no intercepted/mocked data. They are distinct evidence. Network-unavailable, malformed success, 404, 422, 503, recommendation failure, bounded-window exhaustion, slow obsolete mode requests and repeated comparison are included in browser coverage. Assertions verify outgoing query parameters and comparison POST bodies.

Defects found and fixed included a category label containing option text, application-alert assertions colliding with Next's route announcer, ESM fixture imports, top-K control history restoration, identical-query comparison refetching, malformed calendar dates, and learning configured ranking windows from response metadata. Initial certificate errors were resolved using the repository CA bundle; no TLS validation was disabled. Browser tests were rerun after corrections.

## Screenshots

These are actual local browser screenshots, captured from the live backend. Desktop captures include complete pages; phone captures show the viewport at 390×844. They were visually inspected for contrast, typography, wrapping and containment.

- [Homepage](screenshots/live-home.png)
- [Hybrid search results](screenshots/live-search.png)
- [Paper details and related papers](screenshots/live-paper.png)
- [Comparison laboratory with expanded RRF](screenshots/live-compare.png)
- [Mobile semantic search](screenshots/live-mobile-search.png)
- [Mobile comparison](screenshots/live-mobile-compare.png)

## Protected artifact integrity

No retrieval engine, dataset, embeddings, index pipeline, index files or model weights were edited. No indexing or embedding generation was run. SHA256 comparison against the existing Phase 2 baseline confirmed all 45 protected files unchanged. Metadata SHA256 also matches the pre-implementation Phase 4 snapshot. Evidence: [PHASE4_ARTIFACT_INTEGRITY.json](PHASE4_ARTIFACT_INTEGRITY.json).

## Known limitations

- Evaluation judgments, quality metrics and repeated-run benchmark data belong to Phase 5. Current empty charts do not imply measured results.
- The API omits direct RRF configuration. The UI derives the constant from actual returned contributions, checks consistency, and labels its origin; it never hardcodes an example in results.
- A fresh deep link uses verified default ranking-window limits until a response provides configured limits. Different backend settings can yield handled 422 errors.
- Browser coverage uses Chromium and viewport emulation; physical devices, Safari and Firefox were not tested. Math notation remains plain text.
- Full npm audit reports five high-severity development-only entries in one Next lint dependency chain ending in braces; the production audit is clean. ESLint 9.39.5 is deprecated but currently matches Next's plugin peer ranges. ESLint 10 was inspected and conflicts with those plugins. The automated audit fix proposes an incompatible major downgrade, so this upstream tooling maintenance issue is documented rather than hidden or forced.

## Run locally

Repository-root terminal:

```powershell
.\.venv\Scripts\python.exe -m backend.api
```

Second terminal:

```powershell
Set-Location frontend
npm ci
Copy-Item .env.example .env.local
npm run dev
```

Open `http://localhost:3000`. Production: `npm run build`, then `npm start` from `frontend/`. See [FRONTEND_TESTING.md](FRONTEND_TESTING.md) for test commands, Chromium installation, CA setup and runtime permissions. Local verification servers can be restarted with these commands; no hosting deployment was requested.

## Phase 5 readiness

Typed reusable Recharts components accept precision–recall points and measured latency records. The evaluation page already explains Precision@10, Recall@10, MAP and nDCG@10 and reserves truthful empty states. Generated contracts, query hooks, shared loading/error components, methodology and test infrastructure provide the integration foundation for future judged evaluation. No fake evaluation endpoints or relevance judgments were introduced.
