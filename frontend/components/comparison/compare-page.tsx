"use client";
import { useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import type { Filters, Mode, CompareResponse } from "@/lib/api/types";
import { api } from "@/lib/api/client";
import {
  parseState,
  params,
  modes,
  labels,
  querySchema,
  filterSchema,
  paperURL,
  score,
  scoreLabel,
} from "@/lib/state";
import { SearchForm, ModeSelector } from "../search/search-form";
import { FilterForm } from "../search/filters";
import { RankingExplanation } from "../papers/paper-card";
import { ErrorState, EmptyState, LoadingSkeleton } from "../ui/states";
export function ComparisonResults({ data }: { data: CompareResponse }) {
  const [active, setActive] = useState<Mode>("hybrid");
  const papers = new Map(
    Object.values(data.methods).flatMap((s) =>
      s.results.map((r) => [r.paper.id, r.paper] as const),
    ),
  );
  return (
    <>
      <div className="result-meta mt-6">
        <span>
          Current request · {data.timing_ms.total.toFixed(1)} ms overall
        </span>
        <span>
          Method totals attribute shared work; these are not repeated
          benchmarks.
        </span>
      </div>
      <div className="mobile-tabs">
        <ModeSelector mode={active} onChange={setActive} />
      </div>
      <div className="compare-grid">
        {modes.map((m) => {
          const method = data.methods[m];
          return (
            <section
              key={m}
              className={
                "compare-column surface " + (active === m ? "selected" : "")
              }
              aria-label={labels[m] + " rankings"}
            >
              <h2>{labels[m]}</h2>
              <p className="mt-2 text-xs text-secondary">
                {method?.timing_ms.total.toFixed(1)} ms ·{" "}
                {method?.pagination.returned} returned
              </p>
              {method?.results.length ? (
                method.results.map((r) => {
                  const shared = data.rank_differences.find(
                    (d) => d.paper_id === r.paper.id,
                  );
                  const count = Object.values(shared?.ranks || {}).filter(
                    (v) => v !== null,
                  ).length;
                  return (
                    <div key={r.paper.id} className="compare-entry">
                      <div className="rank">
                        RANK {r.rank}
                        {count > 1 && (
                          <span className="tag ml-2">Shared by {count}</span>
                        )}
                      </div>
                      <Link href={paperURL(r.paper.id)}>{r.paper.title}</Link>
                      <div className="score">
                        <strong>{score(r.score, m)}</strong>
                        <span>{scoreLabel(m)}</span>
                      </div>
                      {m === "hybrid" && <RankingExplanation result={r} />}
                    </div>
                  );
                })
              ) : (
                <p className="text-sm text-secondary">
                  No results in this ranking.
                </p>
              )}
            </section>
          );
        })}
      </div>
      <section className="article-section">
        <h2>Ranking overlap</h2>
        <p className="text-sm text-secondary">
          Shared papers in the returned top-K. Overlap describes agreement, not
          relevance quality.
        </p>
        <div className="chips">
          {Object.entries(data.overlaps).map(([pair, ids]) => (
            <span className="tag" key={pair}>
              {pair
                .split(":")
                .map((m) => labels[m as Mode])
                .join(" / ")}
              : {ids.length}
            </span>
          ))}
        </div>
      </section>
      <section className="article-section">
        <h2>Track each paper across methods</h2>
        <p className="text-sm text-secondary">
          A dash means absent from this method’s returned top-K. Δ is second
          rank minus first rank.
        </p>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Paper</th>
                {modes.map((m) => (
                  <th key={m}>{labels[m]}</th>
                ))}
                <th>Δ BM25 → Hybrid</th>
              </tr>
            </thead>
            <tbody>
              {data.rank_differences.map((d) => (
                <tr key={d.paper_id}>
                  <td>
                    <Link href={paperURL(d.paper_id)}>
                      {papers.get(d.paper_id)?.title || d.paper_id}
                    </Link>
                  </td>
                  {modes.map((m) => (
                    <td key={m}>{d.ranks[m] ?? "—"}</td>
                  ))}
                  <td>
                    {d.delta_by_pair["bm25:hybrid"] ??
                      (d.delta_by_pair["hybrid:bm25"] != null
                        ? -d.delta_by_pair["hybrid:bm25"]
                        : "—")}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </>
  );
}
export function ComparePage() {
  const p = useSearchParams();
  const s = parseState(p);
  const router = useRouter();
  const top = Number(p.get("top_k") || 10);
  const valid = querySchema.safeParse(s.q);
  const validFilters = filterSchema.safeParse(s.filters);
  const body = { query: s.q, top_k: top, modes, filters: s.filters };
  const comparison = useQuery({
    queryKey: ["compare", body],
    queryFn: ({ signal }) => api.compare(body, signal),
    enabled:
      valid.success &&
      validFilters.success &&
      Number.isInteger(top) &&
      top >= 1 &&
      top <= 100,
  });
  const navigate = (q: string, filters: Filters) =>
    router.push("/compare?" + params({ q, top_k: top, ...filters }));
  return (
    <>
      <div className="page-heading">
        <div className="eyebrow">The comparison laboratory</div>
        <h1>Different rankings. The same question.</h1>
        <p>
          Inspect how four retrieval methods see the same eligible research
          collection.
        </p>
      </div>
      <SearchForm
        key={s.q}
        initialQuery={s.q}
        showModes={false}
        action="Compare"
        busy={comparison.isFetching}
        onSubmit={(q) => {
          if (q === s.q) comparison.refetch();
          else navigate(q, s.filters);
        }}
      />
      <label className="field mt-5 max-w-48" htmlFor="top-k">
        Results per method
        <select
          id="top-k"
          value={top}
          onChange={(e) => {
            const value = Number(e.target.value);
            router.push(
              "/compare?" + params({ q: s.q, ...s.filters, top_k: value }),
            );
          }}
        >
          {Number.isInteger(top) &&
            top >= 1 &&
            top <= 100 &&
            ![5, 10, 20, 50, 100].includes(top) && <option>{top}</option>}
          {[5, 10, 20, 50, 100].map((k) => (
            <option key={k}>{k}</option>
          ))}
        </select>
      </label>
      <details className="surface p-4">
        <summary>Apply the same filters to every method</summary>
        <div className="mt-5 max-w-lg">
          <FilterForm
            key={JSON.stringify(s.filters)}
            id="compare"
            filters={s.filters}
            onApply={(f) => navigate(s.q, f)}
            onClear={() => navigate(s.q, {})}
          />
        </div>
      </details>
      {!s.q ? (
        <EmptyState
          title="Put the algorithms side by side"
          description="Enter a query to compare actual rankings, overlaps, scores, and timing."
        />
      ) : !valid.success ||
        !validFilters.success ||
        !Number.isInteger(top) ||
        top < 1 ||
        top > 100 ? (
        <EmptyState
          title="Check comparison inputs"
          description="Use a meaningful query, valid filters, and a top-K between 1 and 100."
        />
      ) : comparison.isPending ? (
        <LoadingSkeleton />
      ) : comparison.isError ? (
        <ErrorState
          error={comparison.error}
          retry={() => comparison.refetch()}
        />
      ) : comparison.data ? (
        <ComparisonResults data={comparison.data} />
      ) : null}
    </>
  );
}
