"use client";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api/client";
import { authors, dateLabel, validID } from "@/lib/state";
import { PaperCard, PaperLinks } from "./paper-card";
import { ErrorState, EmptyState, LoadingSkeleton } from "../ui/states";
export function SimilarPapers({ id }: { id: string }) {
  const similar = useQuery({
    queryKey: ["similar", id],
    queryFn: ({ signal }) => api.similar(id, signal),
  });
  return (
    <section className="article-section">
      <div className="eyebrow">Keep exploring</div>
      <h2>Related in meaning</h2>
      <p className="text-secondary text-sm">
        Recommendations use vector cosine similarity.
      </p>
      {similar.isPending ? (
        <LoadingSkeleton />
      ) : similar.isError ? (
        <ErrorState error={similar.error} retry={() => similar.refetch()} />
      ) : similar.data?.results.filter((r) => r.paper.id !== id).length ? (
        similar.data.results
          .filter((r) => r.paper.id !== id)
          .map((r) => <PaperCard key={r.paper.id} result={r} />)
      ) : (
        <EmptyState title="No recommendations available" />
      )}
    </section>
  );
}
export function PaperPage() {
  const id = useSearchParams().get("arxiv_id") || "";
  const paper = useQuery({
    queryKey: ["paper", id],
    queryFn: ({ signal }) => api.paper(id, signal),
    enabled: validID(id),
  });
  if (!validID(id))
    return (
      <EmptyState
        title="Select a valid paper"
        description="Open a paper from search results or provide its stable ArXiv identifier."
      />
    );
  if (paper.isPending) return <LoadingSkeleton />;
  if (paper.isError)
    return <ErrorState error={paper.error} retry={() => paper.refetch()} />;
  const p = paper.data;
  return (
    <article className="article">
      <Link href="/search" className="text-primary text-sm">
        ← Search the collection
      </Link>
      <div className="eyebrow mt-8">Research paper · {p.id}</div>
      <h1>{p.title}</h1>
      <p className="authors">{authors(p)}</p>
      <div className="tags">
        {p.categories.map((c) => (
          <span key={c} className="tag">
            {c}
          </span>
        ))}
      </div>
      <div className="metadata">
        {dateLabel(p.published_at) && (
          <span>Published {dateLabel(p.published_at)}</span>
        )}
        {dateLabel(p.updated_at) && (
          <span>Updated {dateLabel(p.updated_at)}</span>
        )}
      </div>
      <div className="paper-actions">
        <PaperLinks id={p.id} />
      </div>
      <section className="article-section surface p-6 md:p-8">
        <h2>Abstract</h2>
        <p className="abstract">{p.abstract}</p>
      </section>
      {(p.doi || p.journal_ref || p.comments) && (
        <section className="article-section">
          <h2>Publication notes</h2>
          {p.doi && <p className="text-sm break-words">DOI: {p.doi}</p>}
          {p.journal_ref && (
            <p className="text-sm">Journal reference: {p.journal_ref}</p>
          )}
          {p.comments && <p className="text-sm">{p.comments}</p>}
        </section>
      )}
      <SimilarPapers id={p.id} />
    </article>
  );
}
