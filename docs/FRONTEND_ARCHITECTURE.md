# Frontend architecture

Phase 4 lives in `frontend/`. It uses Next.js 16.4 App Router, React 19, strict TypeScript, Tailwind 4, manually installed shadcn-style Button and Radix Sheet primitives, Lucide, TanStack Query, React Hook Form/Zod, next-themes, and Recharts. Dependencies are pinned and a lockfile is checked in. No retrieval algorithms execute in the browser.

## Routes and components

| Route | Implemented behavior |
| --- | --- |
| `/` | Hybrid-default search, selectable algorithms, suggested queries, actual corpus statistics, method explanations |
| `/search` | URL-owned search, all four algorithms, category/subject/year/author filters, result cards, bounded pagination, native scores and explanations |
| `/papers?arxiv_id=...` | Full metadata, text-preserved abstract, safe external links, independently loaded recommendations |
| `/compare` | One consistent comparison request, shared filters, top-K, method columns/mobile selector, overlaps, rank table, RRF contributions, timing |
| `/evaluation` | Query collection versions, frozen pools, readiness, immutable run history, measured metrics/curves, benchmarks and exports |
| `/evaluation/judge` | Blind paper assessment, persistent grades, progress, keyboard controls, navigation and draft protection |
| `/about` | Dataset, methods, architecture, limitations, live health and provenance |
| unknown route | Not-found experience with search link |

Page entry points and layout are server components. Interactive feature components use client boundaries. The layout wraps URL-dependent components in Suspense. Providers own a single QueryClient and persistent theme management. The header provides active navigation, a mobile Sheet and theme toggle. Footer attributes arXiv and explains independent project status.

## State ownership

Search state belongs to `q`, `mode`, `category`, `subject`, `year_from`, `year_to`, `author`, and `offset` URL parameters. Comparison uses `q`, `top_k`, and the same filters. Router pushes preserve Back/Forward behavior; query, mode, and filter changes reset offset. Search forms and filter drafts use local state. Filters require explicit Apply; typing author text does not trigger searches. Remount keys restore form defaults from the URL. Filter chips remove individual applied fields. Desktop filters and mobile Sheet use separate input IDs.

TanStack Query owns server state. Complete search state is part of each query key. Fetch consumes Query's AbortSignal and adds a 60-second timeout, preventing obsolete requests from replacing newer queries. Default retries are disabled to avoid silently repeating expensive CPU retrieval; recoverable errors provide explicit Retry. Categories cache for one hour, stats for five minutes, other queries for one minute. Focus does not trigger refetch. Resubmitting an identical search or comparison explicitly refetches.

## Presentation and accessibility

Semantic CSS tokens support light/dark palettes. Desktop search uses a 240px filter column; mobile uses a modal, focus-managed Radix Sheet. Comparison uses four columns on wide screens, two on tablets, and one selected column on phones. Tables scroll inside their own containers. Cards wrap long titles, categories and author text; abstracts initially clamp to three lines and can expand. React renders metadata as escaped text and preserves original abstract content, including LaTeX.

Forms have labels, validation feedback, visible focus, named algorithm groups, pressed states, disabled submission while fetching, and loading status regions. The shell includes a skip link and current-route indicators. Shared states cover empty results, invalid inputs, unavailability, not-ready indexes, timeouts, malformed responses, and unknown papers. Mathematical rendering is deliberately text-only.

## Phase 5 extension points

`components/evaluation/charts.tsx` exports typed precision–recall and measured-latency components with honest empty states and SVG downloads. Phase 5 provides evaluation contracts, Zod boundaries and TanStack Query requests in `lib/api/evaluation.ts` and `components/evaluation`. Current search/comparison timing and overlap are never reused as judged quality metrics. See `EVALUATION_ARCHITECTURE.md` for the implemented storage and snapshot workflow.
