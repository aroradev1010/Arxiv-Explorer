# Frontend API integration

## Authoritative contract

Before implementation, API documentation, Pydantic schemas, routers, configuration, service orchestration and API fixtures were inspected. The running backend's `openapi.json` was captured in `frontend/openapi.json`. `frontend/lib/api/generated.ts` is generated with:

```powershell
Set-Location frontend
Invoke-WebRequest http://127.0.0.1:8000/openapi.json -OutFile openapi.json
npx --no-install openapi-typescript openapi.json -o lib/api/generated.ts
```

Domain aliases reuse generated schemas; runtime Zod checks reject malformed successful responses. The API client is the only production fetch boundary. Set `NEXT_PUBLIC_API_BASE_URL` in `.env.local` (default `http://127.0.0.1:8000`). It must be reachable by the browser; it is not a secret. The frontend calls FastAPI directly. Existing CORS permits `http://localhost:3000` and `http://127.0.0.1:3000`; backend configuration was not changed. No Docker deployment was added. Remote browser/container deployment needs a reachable HTTPS backend address and appropriate existing CORS configuration, rather than a loopback address.

## Endpoint mapping

| Endpoint | Consumer |
| --- | --- |
| GET `/api/v1/search` | Search page; safely encoded query, mode, filters, limit and offset |
| GET `/api/v1/papers` | Detail metadata using query parameter ID, including legacy slashes |
| GET `/api/v1/papers/similar` | Independent recommendation query, limit 5; source ID excluded again in presentation |
| GET `/api/v1/categories` | Indexed category and subject options, only authoritative names or codes |
| POST `/api/v1/compare` | All four modes, one query, one filter set, selected top-K |
| GET `/api/v1/system/stats` | Homepage values and About provenance |
| GET `/api/v1/health/live` | About process health |
| GET `/api/v1/health/ready` | About index readiness; its 503 health shape is handled independently |

## Correctness decisions

Queries contain a Unicode letter/number and have at most 1,000 characters. Years are 1991–2100 with From <= To. Filters combine with AND. Author text is limited to 200 characters. The backend remains authoritative for validation; 422 errors appear as useful messages. Invalid URL filter values remain visible and stop requests instead of silently broadening the search.

Initial page requests use the verified defaults: 10 results, native window 1,000, hybrid window 200. Subsequent navigation learns each mode's actual window from returned cached search metadata, respects `has_more`, and shortens the last request when required. A fresh deep link uses conservative default windows because there is no window-configuration endpoint. Changed server limits can return 422, which is surfaced without a crash. There are no unlimited page counts. Ranks come from the API; candidate counts refer to the bounded window, not corpus-wide relevance.

Structured author lists fall back to `authors_text` when empty. Dates are omitted if missing/unparseable. DOI/journal/notes appear only when present. Native scores keep original numeric values and use mode-specific labels/precision; they are not probabilities. Lexical explanation tokens are displayed as highlighted indexed terms (possibly stemmed), without pretending they are exact surface-word matches. Semantic descriptions avoid causal claims.

RRF rank, native score and contribution come directly from `ranking_details.contributions`. Absent native methods show zero contribution. The UI sums returned contributions and checks agreement with the fused score. The API does not expose `rrf_k` in stats or comparison responses. The displayed constant is derived from `1/contribution - rank`, checked for agreement across present methods, and explicitly labeled as derived; it is not a hardcoded illustrative constant. Actual current API data yields 60.

Comparison overlap and per-paper ranks/deltas use backend values. A dash means absence from returned top-K. Timing is current-request milliseconds, with comparison method totals attributed from shared work. It is not a formal benchmark. Error envelopes and readiness health responses are distinct; sanitized service errors, network failures, unreadable responses, schema mismatches, cancellation and timeouts are supported.

External links are constructed exclusively from validated stable IDs under `https://arxiv.org/abs/` or `/pdf/`, with `noopener noreferrer`. API-provided arbitrary URL fields are never trusted as navigation targets. Paper identifiers are encoded by URLSearchParams for internal routes and requests. No unsafe HTML injection is used.

## Contract findings and limits

Existing `docs/API.md` agrees with runtime search response shapes and constraints. Ranking windows and native scores were confirmed rather than assumed. No authoritative category names exist for many entries, so codes are displayed. Phase 5 adds real evaluation endpoints and typed responses under `/api/v1/evaluation`; see `EVALUATION_API.md`. The client validates these responses and keeps judgment-based effectiveness separate from search scores and one-request timing.
