# Frontend testing and local development

Use Node 22.19 or newer supported by the pinned packages, npm, and the repository's existing Python environment. Tested on Windows PowerShell. Install from the lockfile:

```powershell
Set-Location frontend
npm ci
Copy-Item .env.example .env.local
```

On this machine the network uses the existing repository CA bundle. If normal npm downloads report a certificate-chain error:

```powershell
npm ci --cafile ../.bootstrap-certs.pem
$env:NODE_EXTRA_CA_CERTS = (Resolve-Path ../.bootstrap-certs.pem).Path
```

Start backend in a repository-root terminal (do not rerun indexing):

```powershell
.\.venv\Scripts\python.exe -m backend.api
```

Start frontend in a second terminal:

```powershell
Set-Location frontend
npm run dev
```

Open `http://localhost:3000` or `http://127.0.0.1:3000`. The backend serves `http://127.0.0.1:8000` and Swagger `/docs`. For production locally, use `npm run build`, then `npm start`.

## Checks

Run in `frontend/`:

```powershell
npm run typecheck
npm run lint
npm test
npm run build
npx --no-install playwright install chromium
npm run test:e2e
npm run test:live
```

The last command requires the real backend to be ready. Playwright configurations start Next.js if no existing server responds. Chromium runs desktop and iPhone-sized mobile tests; this is viewport emulation, not a claim of physical-device Safari testing. Live output uses a separate directory to avoid collisions with fixture test output. On this managed environment Vite, Next.js builds, and browser spawning require approved child-process execution.

Unit/component/API tests cover URL encoding/restoration, query/year validation, mode handling, raw author fallback, native score formatting, safe legacy links, RRF summation, pagination boundaries, API errors/schema checks, request parameters, search submission, algorithm selection, filters, cards, details, recommendations, comparison table and empty/error states. Network-boundary mocks use explicitly marked actual API snapshots under `tests/fixtures/`; synthetic legacy/error cases are test-only. Production code never imports test fixtures.

Browser tests cover homepage search, switching and history, filter requests/reset/restoration, details, external links, comparison payloads/RRF, unavailable service/retry/empty/422, theme persistence, screenshots, mobile navigation, malformed responses, legacy IDs/404, independent recommendations, pagination bounds, obsolete slow requests, top-K/repeated comparison/filter/history, and widths 360/768/1024.

Read-only real API and artifact audits, run from repository root:

```powershell
.\.venv\Scripts\python.exe frontend/scripts/live-smoke.py
.\.venv\Scripts\python.exe frontend/scripts/integrity.py
```

Live smoke checks all four modes, combined filtering, exact metadata consistency, five recommendations, and comparison contributions. It records `docs/PHASE4_LIVE_SMOKE.json` and refreshes explicitly marked test snapshots. Integrity hashes all protected artifacts against the existing Phase 2 baseline and compares metadata SHA256 against the Phase 4 pre-implementation snapshot. It never rebuilds indexes, modifies data, or downloads models.

## Dependency limitations

Production `npm audit --omit=dev` reports zero vulnerabilities at verification time. Full audit reports five high-severity entries in one development-only chain: eslint-config-next → Next ESLint plugin → fast-glob → micromatch → braces (stack exhaustion with malicious nested glob patterns). npm's proposed automatic fix downgrades the Next lint configuration to a different major version; it was not applied blindly. ESLint 9.39.5 is pinned for compatibility with current Next lint plugins; npm marks it deprecated, while ESLint 10 produces unsupported plugin peer ranges. This tooling maintenance limitation requires upstream-compatible upgrades; production runtime dependencies are unaffected. Do not use `npm audit fix --force` without reviewing the resulting stack.

See `docs/PHASE4_REPORT.md` for actual command outcomes and representative screenshots.
