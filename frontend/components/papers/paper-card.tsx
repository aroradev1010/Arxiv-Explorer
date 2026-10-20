"use client";
import Link from "next/link";
import { useState } from "react";
import type { RankedPaper } from "@/lib/api/types";
import {
  authors,
  dateLabel,
  documentURL,
  paperURL,
  score,
  scoreLabel,
  labels,
  fusionSummary,
} from "@/lib/state";
export function PaperLinks({ id }: { id: string }) {
  const arxiv = documentURL(id);
  const pdf = documentURL(id, true);
  return (
    <>
      {arxiv && (
        <a href={arxiv} target="_blank" rel="noopener noreferrer">
          View on arXiv ↗
        </a>
      )}
      {pdf && (
        <a href={pdf} target="_blank" rel="noopener noreferrer">
          Open PDF ↗
        </a>
      )}
    </>
  );
}
export function RankingExplanation({ result }: { result: RankedPaper }) {
  const d = result.ranking_details;
  const summary = fusionSummary(result);
  return (
    <>
      {d.matched_indexed_tokens?.length ? (
        <div className="mt-3 text-xs text-secondary">
          Matched indexed tokens:{" "}
          {d.matched_indexed_tokens.map((t) => (
            <mark key={t} className="tag mr-1">
              {t}
            </mark>
          ))}
          <span className="block mt-1">Indexed tokens may be stemmed.</span>
        </div>
      ) : null}
      {d.cosine_similarity != null && (
        <p className="mt-3 mb-0 text-xs text-secondary">
          Vector cosine similarity: {score(d.cosine_similarity, "semantic")}.
          This measures closeness in embedding space.
        </p>
      )}
      {d.contributions && (
        <details>
          <summary>Explore RRF contributions</summary>
          <p className="mt-3">
            RRF(d) = Σ 1 / (k + rankᵢ(d))
            {summary.k !== null
              ? ` · k = ${summary.k} (derived from returned contributions)`
              : " · fusion constant not exposed by API"}
          </p>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Method</th>
                  <th>Rank</th>
                  <th>Native score</th>
                  <th>Contribution</th>
                </tr>
              </thead>
              <tbody>
                {(["tfidf", "bm25", "semantic"] as const).map((m) => {
                  const c = d.contributions?.[m];
                  return (
                    <tr key={m}>
                      <td>{labels[m]}</td>
                      <td>{c?.rank ?? "—"}</td>
                      <td>{c ? score(c.native_score, m) : "—"}</td>
                      <td>{c ? c.contribution.toFixed(8) : "0 (absent)"}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          <p className="mt-3">
            Sum: {summary.sum.toFixed(8)} · Fused score:{" "}
            {result.score.toFixed(8)} · Position {result.rank}.{" "}
            {summary.matches
              ? "Contributions agree within numerical precision."
              : "Contribution total differs from the returned score."}
          </p>
        </details>
      )}
    </>
  );
}
export function PaperCard({ result }: { result: RankedPaper }) {
  const [expanded, setExpanded] = useState(false);
  const p = result.paper;
  return (
    <article className="paper-card surface">
      <div className="paper-top">
        <div>
          <div className="rank">
            RANK {result.rank.toString().padStart(2, "0")} · {p.id}
          </div>
          <h2>
            <Link href={paperURL(p.id)}>{p.title}</Link>
          </h2>
          <div className="authors">
            {authors(p)}
            {dateLabel(p.published_at) && <> · {dateLabel(p.published_at)}</>}
          </div>
        </div>
        <div
          className="score"
          title="Native ranking score, not a relevance probability"
        >
          <strong>{score(result.score, result.algorithm)}</strong>
          <span>{scoreLabel(result.algorithm)}</span>
        </div>
      </div>
      <div className="tags">
        {p.categories.map((c) => (
          <span key={c} className="tag">
            {c}
          </span>
        ))}
      </div>
      <p className={"abstract " + (expanded ? "" : "clamp")}>{p.abstract}</p>
      <div className="paper-actions">
        <button
          type="button"
          className="text-primary"
          onClick={() => setExpanded(!expanded)}
          aria-expanded={expanded}
        >
          {expanded ? "Collapse abstract" : "Expand abstract"}
        </button>
        <Link href={paperURL(p.id)}>Paper details</Link>
        <PaperLinks id={p.id} />
      </div>
      <RankingExplanation result={result} />
    </article>
  );
}
