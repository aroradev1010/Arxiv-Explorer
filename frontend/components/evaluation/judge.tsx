"use client";
import { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { evaluationApi, type JudgmentDocument } from "@/lib/api/evaluation";
import { Button } from "@/components/ui/button";
import { ErrorState, EmptyState } from "@/components/ui/states";

export function JudgeWorkspace() {
  const params = useSearchParams();
  const [poolChoice, setPool] = useState(params.get("pool") || "");
  const [queryChoice, setQuery] = useState("");
  const [offset, setOffset] = useState(0);
  const [text, setText] = useState("");
  const [dirty, setDirty] = useState(false);
  const pools = useQuery({
    queryKey: ["evaluation", "pools"],
    queryFn: ({ signal }) => evaluationApi.pools(signal),
  });
  const config = useQuery({
    queryKey: ["evaluation", "config"],
    queryFn: ({ signal }) => evaluationApi.config(signal),
  });
  const poolId =
    poolChoice || pools.data?.find((p) => p.status === "COMPLETED")?.id || "";
  const pool = pools.data?.find((p) => p.id === poolId);
  const queryId = pool?.metadata.queries.some((q) => q.id === queryChoice)
    ? queryChoice
    : pool?.metadata.queries[0]?.id || "";
  const q = pool?.metadata.queries.find((q) => q.id === queryId);
  const documents = useQuery({
    queryKey: ["evaluation", "documents", poolId, queryId, offset, text],
    queryFn: ({ signal }) =>
      evaluationApi.documents(poolId, queryId, offset, text, signal),
    enabled: !!poolId && !!queryId,
  });
  const progress = useQuery({
    queryKey: ["evaluation", "progress", poolId],
    queryFn: ({ signal }) => evaluationApi.progress(poolId, signal),
    enabled: !!poolId,
  });
  const p = progress.data?.queries.find((p) => p.query_id === queryId);
  const guard = (action: () => void) => {
    if (!dirty || window.confirm("Discard unsaved relevance changes?")) {
      setDirty(false);
      action();
    }
  };
  const error =
    pools.error || config.error || documents.error || progress.error;
  return (
    <>
      <div className="page-heading">
        <div className="eyebrow">Human relevance assessment</div>
        <h1>Judge the information need.</h1>
        <p>
          Assess title and abstract. Candidate order is shuffled; retrieval
          methods, scores, and ranks are hidden.
        </p>
        <Link href="/evaluation">Return to query list</Link>
      </div>
      {error ? (
        <ErrorState
          error={error}
          retry={() => {
            pools.refetch();
            documents.refetch();
            progress.refetch();
          }}
        />
      ) : null}
      <section className="surface evaluation-section">
        <div className="evaluation-actions">
          <label>
            Candidate pool
            <select
              aria-label="Candidate pool"
              value={poolId}
              onChange={(e) =>
                guard(() => {
                  setPool(e.target.value);
                  setOffset(0);
                  setQuery("");
                })
              }
            >
              <option value="">Choose a pool</option>
              {pools.data
                ?.filter((p) => p.status === "COMPLETED")
                .map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.id}
                    {p.stale ? " · stale" : ""}
                  </option>
                ))}
            </select>
          </label>
          <label>
            Evaluation query
            <select
              aria-label="Evaluation query"
              value={queryId}
              onChange={(e) =>
                guard(() => {
                  setQuery(e.target.value);
                  setOffset(0);
                  setText("");
                })
              }
            >
              {pool?.metadata.queries.map((q) => (
                <option key={q.id} value={q.id}>
                  {q.id} · {q.query}
                </option>
              ))}
            </select>
          </label>
        </div>
        {q ? (
          <>
            <h2>
              {q.id} · {q.query}
            </h2>
            <p className="my-3">{q.information_need}</p>
            <p className="text-secondary">
              {q.domain} · {q.query_type}
            </p>
          </>
        ) : null}
        {p ? (
          <>
            <p role="status">
              {p.judged}/{p.total} judged · {p.unjudged} unjudged ·{" "}
              {p.percent.toFixed(1)}% complete
            </p>
            <progress
              aria-label="Query judgment progress"
              max={p.total || 1}
              value={p.judged}
            />
            <p>
              Grade 0: {p.grades["0"]} · Grade 1: {p.grades["1"]} · Grade 2:{" "}
              {p.grades["2"]} · {p.missing_required} required judgments remain
            </p>
          </>
        ) : null}
        <label>
          Search within this pool
          <input
            type="search"
            value={text}
            onChange={(e) =>
              guard(() => {
                setText(e.target.value);
                setOffset(0);
              })
            }
          />
        </label>
        <a href={evaluationApi.exportUrl("judgments", poolId, "csv")}>
          Export judgments CSV
        </a>
      </section>
      {documents.isFetching ? (
        <p role="status">Loading candidate papers…</p>
      ) : null}
      {documents.data?.items.length ? (
        <JudgmentSession
          key={poolId + queryId + offset + text}
          poolId={poolId}
          items={documents.data.items}
          writable={config.data?.mutations_enabled === true && !pool?.stale}
          onDirty={setDirty}
        />
      ) : documents.data ? (
        <EmptyState
          title="No matching papers"
          description="Choose a completed pool or adjust the pool search."
        />
      ) : null}
      <div className="evaluation-actions">
        <Button
          variant="outline"
          disabled={!offset}
          onClick={() => guard(() => setOffset(Math.max(0, offset - 100)))}
        >
          Previous 100 candidates
        </Button>
        <p>
          {offset + 1}–{offset + (documents.data?.items.length || 0)} of{" "}
          {documents.data?.total || 0}
        </p>
        <Button
          variant="outline"
          disabled={!documents.data || offset + 100 >= documents.data.total}
          onClick={() => guard(() => setOffset(offset + 100))}
        >
          Next 100 candidates
        </Button>
      </div>
    </>
  );
}

function JudgmentSession({
  poolId,
  items,
  writable,
  onDirty,
}: {
  poolId: string;
  items: JudgmentDocument[];
  writable: boolean;
  onDirty: (dirty: boolean) => void;
}) {
  const [index, setIndex] = useState(() =>
    Math.max(
      0,
      items.findIndex((p) => p.relevance_grade === null),
    ),
  );
  const [dirty, setDirty] = useState(false);
  const [auto, setAuto] = useState(true);
  const move = (next: number) => {
    if (!dirty || window.confirm("Discard unsaved relevance changes?")) {
      setDirty(false);
      onDirty(false);
      setIndex(next);
    }
  };
  const nextUnjudged = () => {
    const next = items.findIndex(
      (p, i) => i > index && p.relevance_grade === null,
    );
    const wrap = items.findIndex(
      (p, i) => i < index && p.relevance_grade === null,
    );
    return next >= 0 ? next : wrap;
  };
  return (
    <>
      <div className="evaluation-actions">
        <label>
          Jump to paper
          <select
            aria-label="Jump to paper"
            value={index}
            onChange={(e) => move(Number(e.target.value))}
          >
            {items.map((p, i) => (
              <option key={p.paper_id} value={i}>
                {i + 1} · {p.paper.title} ·{" "}
                {p.relevance_grade === null
                  ? "Unjudged"
                  : "Grade " + p.relevance_grade}
              </option>
            ))}
          </select>
        </label>
        <label>
          <input
            type="checkbox"
            checked={auto}
            onChange={(e) => setAuto(e.target.checked)}
          />{" "}
          Advance to next unjudged after saving
        </label>
      </div>
      <JudgmentCard
        key={items[index].paper_id}
        poolId={poolId}
        document={items[index]}
        writable={writable}
        onDirty={(value) => {
          setDirty(value);
          onDirty(value);
        }}
        onSaved={() => {
          setDirty(false);
          onDirty(false);
          if (auto) {
            const next = nextUnjudged();
            if (next >= 0) setIndex(next);
          }
        }}
      />
      <div className="evaluation-actions">
        <Button
          variant="outline"
          disabled={index === 0}
          onClick={() => move(index - 1)}
        >
          Previous paper
        </Button>
        <Button
          variant="outline"
          disabled={index === items.length - 1}
          onClick={() => move(index + 1)}
        >
          Next paper
        </Button>
        <Button
          variant="outline"
          disabled={nextUnjudged() < 0}
          onClick={() => move(nextUnjudged())}
        >
          Next unjudged
        </Button>
      </div>
    </>
  );
}

export function JudgmentCard({
  poolId,
  document,
  writable,
  onDirty,
  onSaved,
}: {
  poolId: string;
  document: JudgmentDocument;
  writable: boolean;
  onDirty: (dirty: boolean) => void;
  onSaved: () => void;
}) {
  const cache = useQueryClient();
  const [grade, setGrade] = useState<number | null>(document.relevance_grade);
  const [savedGrade, setSavedGrade] = useState<number | null>(
    document.relevance_grade,
  );
  const [message, setMessage] = useState("");
  const dirty = grade !== savedGrade;
  const select = useCallback(
    (value: number | null) => {
      setGrade(value);
      setMessage("");
      onDirty(value !== savedGrade);
    },
    [onDirty, savedGrade],
  );
  const save = useMutation({
    mutationFn: () =>
      evaluationApi.judge(poolId, document.query_id, document.paper_id, grade),
    onSuccess: () => {
      setSavedGrade(grade);
      setMessage("Judgment saved.");
      cache.invalidateQueries({ queryKey: ["evaluation"] });
      onSaved();
    },
  });
  useEffect(() => {
    const keyboard = (e: KeyboardEvent) => {
      const element = e.target;
      if (
        !writable ||
        save.isPending ||
        e.ctrlKey ||
        e.metaKey ||
        e.altKey ||
        (element instanceof HTMLElement &&
          (element.matches("input,textarea,select") ||
            element.isContentEditable))
      )
        return;
      if (["0", "1", "2"].includes(e.key)) {
        e.preventDefault();
        select(Number(e.key));
      }
    };
    const beforeUnload = (e: BeforeUnloadEvent) => {
      if (dirty) {
        e.preventDefault();
        e.returnValue = "";
      }
    };
    const navigate = (e: MouseEvent) => {
      const target =
        e.target instanceof Element ? e.target.closest("a[href]") : null;
      if (
        dirty &&
        target instanceof HTMLAnchorElement &&
        target.target !== "_blank" &&
        !window.confirm("Discard unsaved relevance changes?")
      ) {
        e.preventDefault();
        e.stopPropagation();
      }
    };
    window.addEventListener("keydown", keyboard);
    window.addEventListener("beforeunload", beforeUnload);
    window.document.addEventListener("click", navigate, true);
    return () => {
      window.removeEventListener("keydown", keyboard);
      window.removeEventListener("beforeunload", beforeUnload);
      window.document.removeEventListener("click", navigate, true);
    };
  }, [dirty, select, writable, save.isPending]);
  useEffect(() => {
    if (!dirty) return;
    // The same-route entry lets us ask before Next.js can unmount the draft.
    const currentUrl = window.location.href;
    const marker = { ...window.history.state, evaluationDraft: true };
    window.history.pushState(marker, "", currentUrl);
    let leaving = false;
    const backNavigation = () => {
      if (leaving) return;
      if (window.confirm("Discard unsaved relevance changes?")) {
        leaving = true;
        window.history.back();
      } else {
        window.history.pushState(marker, "", currentUrl);
      }
    };
    window.addEventListener("popstate", backNavigation);
    return () => {
      window.removeEventListener("popstate", backNavigation);
      if (
        !leaving &&
        window.history.state?.evaluationDraft &&
        window.location.href === currentUrl
      ) {
        window.history.back();
      }
    };
  }, [dirty]);
  const p = document.paper;
  return (
    <article className="surface evaluation-section">
      <h2>{p.title}</h2>
      <p className="mt-3">
        {p.authors.length ? p.authors.join(", ") : p.authors_text}
      </p>
      <p className="text-secondary">
        {p.categories.join(" · ")} ·{" "}
        {p.published_at?.slice(0, 4) || "Year unavailable"} · {p.id}
      </p>
      <p className="my-6 whitespace-pre-wrap">{p.abstract}</p>
      <a href={p.arxiv_url} target="_blank" rel="noopener noreferrer">
        Read on ArXiv ↗
      </a>
      <fieldset className="my-6" disabled={!writable || save.isPending}>
        <legend>Relevance grade (shortcuts 0, 1, 2)</legend>
        <div className="evaluation-actions">
          {[
            [0, "Not relevant (0)"],
            [1, "Partially relevant (1)"],
            [2, "Highly relevant (2)"],
            [null, "Leave unjudged"],
          ].map(([v, label]) => (
            <label key={String(v)}>
              <input
                type="radio"
                name="grade"
                checked={grade === v}
                onChange={() => select(v as number | null)}
              />
              {label}
            </label>
          ))}
        </div>
      </fieldset>
      <p>
        {grade === null ? "Unjudged" : "Selected grade " + grade}
        {dirty ? " · Unsaved changes" : ""}
      </p>
      <Button
        disabled={!writable || save.isPending}
        onClick={() => save.mutate()}
      >
        {save.isPending ? "Saving…" : "Save judgment"}
      </Button>
      <p aria-live="polite">{message}</p>
      {save.error ? (
        <ErrorState error={save.error} retry={() => save.mutate()} />
      ) : null}
    </article>
  );
}
