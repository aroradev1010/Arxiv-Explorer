"use client";
import { useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { SlidersHorizontal } from "lucide-react";
import { api } from "@/lib/api/client";
import type { Filters, SearchResponse } from "@/lib/api/types";
import {
  parseState,
  searchURL,
  querySchema,
  filterSchema,
  canNext,
  labels,
  nextLimit,
} from "@/lib/state";
import { SearchForm, ModeSelector } from "./search-form";
import { FilterForm } from "./filters";
import { PaperCard } from "../papers/paper-card";
import { Button } from "../ui/button";
import { Sheet } from "../ui/sheet";
import { EmptyState, ErrorState, LoadingSkeleton } from "../ui/states";
export function SearchPage() {
  const p = useSearchParams();
  const router = useRouter();
  const client = useQueryClient();
  const s = parseState(p);
  const [open, setOpen] = useState(false);
  const valid = querySchema.safeParse(s.q);
  const filtered = filterSchema.safeParse(s.filters);
  const known = client
    .getQueriesData<SearchResponse>({ queryKey: ["search"] })
    .find(([, data]) => data?.mode === s.mode)?.[1];
  const fallbackWindow =
    known?.pagination.ranking_window_size ?? (s.mode === "hybrid" ? 200 : 1000);
  const validOffset = s.offset < fallbackWindow;
  const limit = Math.min(10, fallbackWindow - s.offset);
  const results = useQuery({
    queryKey: ["search", s, limit],
    queryFn: ({ signal }) => api.search(s, signal, limit),
    enabled: valid.success && filtered.success && validOffset,
  });
  const change = (filters: Filters) => {
    router.push(searchURL({ ...s, filters, offset: 0 }));
    setOpen(false);
  };
  const filterKey = JSON.stringify(s.filters);
  return (
    <>
      <div className="page-heading">
        <div className="eyebrow">The research collection</div>
        <h1>Find your next connection.</h1>
      </div>
      <SearchForm
        key={s.q + ":" + s.mode}
        initialQuery={s.q}
        initialMode={s.mode}
        showModes={false}
        busy={results.isFetching}
        onSubmit={(q, mode) => {
          if (q === s.q && mode === s.mode && s.offset === 0) results.refetch();
          else router.push(searchURL({ ...s, q, mode, offset: 0 }));
        }}
      />
      <ModeSelector
        mode={s.mode}
        onChange={(mode) => router.push(searchURL({ ...s, mode, offset: 0 }))}
      />
      <div className="search-layout">
        <aside className="desktop-filters surface filter-panel">
          <FilterForm
            key={filterKey}
            filters={s.filters}
            onApply={change}
            onClear={() => change({})}
          />
        </aside>
        <section aria-label="Search results">
          <div className="mb-4 md:hidden">
            <Sheet
              title="Research filters"
              open={open}
              onOpenChange={setOpen}
              trigger={
                <Button variant="outline">
                  <SlidersHorizontal size={16} />
                  Filters
                </Button>
              }
            >
              <FilterForm
                id="mobile"
                key={filterKey}
                filters={s.filters}
                onApply={change}
                onClear={() => change({})}
              />
            </Sheet>
          </div>
          <div className="chips">
            {Object.entries(s.filters)
              .filter(([, v]) => v != null)
              .map(([key, v]) => (
                <button
                  className="tag"
                  key={key}
                  aria-label={"Remove " + key + " filter"}
                  onClick={() => {
                    const filters = { ...s.filters };
                    delete filters[key as keyof Filters];
                    change(filters);
                  }}
                >
                  {key.replaceAll("_", " ")}: {v} ×
                </button>
              ))}
          </div>
          {!s.q ? (
            <EmptyState
              title="A question is a good place to start"
              description="Enter a topic or scientific concept to explore the indexed papers."
            />
          ) : !valid.success ? (
            <EmptyState
              title="Check your query"
              description={valid.error.issues[0].message}
            />
          ) : !filtered.success ? (
            <EmptyState
              title="Check your filters"
              description={filtered.error.issues[0].message}
            />
          ) : !validOffset ? (
            <EmptyState
              title="Ranking window exhausted"
              description={`This method supports the first ${fallbackWindow} ranked candidates. Start at an earlier page.`}
            />
          ) : results.isPending ? (
            <LoadingSkeleton />
          ) : results.isError ? (
            <ErrorState error={results.error} retry={() => results.refetch()} />
          ) : results.data ? (
            <>
              <div className="result-meta">
                <span>
                  {labels[results.data.mode]} ·{" "}
                  {results.data.pagination.returned} returned ·{" "}
                  {results.data.timing_ms.total.toFixed(1)} ms
                </span>
                <span title="Candidates are not the total relevant papers in the corpus">
                  {results.data.pagination.ranked_candidate_count} ranked
                  candidates / window{" "}
                  {results.data.pagination.ranking_window_size}
                </span>
              </div>
              {results.data.results.length ? (
                results.data.results.map((r) => (
                  <PaperCard key={r.paper.id} result={r} />
                ))
              ) : (
                <EmptyState />
              )}
              <div className="pagination">
                <Button
                  variant="outline"
                  disabled={!s.offset || results.isFetching}
                  onClick={() =>
                    router.push(
                      searchURL({ ...s, offset: Math.max(0, s.offset - 10) }),
                    )
                  }
                >
                  Previous
                </Button>
                <span>
                  Ranks {results.data.results.length ? s.offset + 1 : 0}–
                  {s.offset + results.data.pagination.returned} · bounded
                  ranking window
                </span>
                <Button
                  variant="outline"
                  disabled={
                    !canNext(results.data.pagination) || results.isFetching
                  }
                  onClick={() => {
                    const next = s.offset + results.data.pagination.limit;
                    if (nextLimit(results.data!.pagination) > 0)
                      router.push(searchURL({ ...s, offset: next }));
                  }}
                >
                  Next
                </Button>
              </div>
            </>
          ) : null}
        </section>
      </div>
    </>
  );
}
