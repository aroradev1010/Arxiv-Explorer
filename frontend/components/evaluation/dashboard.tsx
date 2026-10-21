import { MeasuredCurves, type CurvePoint } from "./charts";
import { labels } from "@/lib/state";
import type { Mode } from "@/lib/api/types";

// Only pass results calculated from genuine, complete relevance judgments.
export interface EvaluationResults {
  metrics: Record<
    Mode,
    {
      precision: number | null;
      pooled_recall: number | null;
      ap: number | null;
      ndcg: number | null;
    }
  >;
  curves: CurvePoint[];
}

const metrics = [
  ["Precision@10", "precision"],
  ["Pooled Recall@10", "pooled_recall"],
  ["MAP@10", "ap"],
  ["nDCG@10", "ndcg"],
] as const;
const modes = ["tfidf", "bm25", "semantic", "hybrid"] as const;

export function EvaluationDashboard({
  results,
}: {
  results?: EvaluationResults;
}) {
  return (
    <div>
      <div className="page-heading">
        <h1>Search Evaluation</h1>
        <p>Compare retrieval quality across four search methods.</p>
      </div>
      <section
        className="surface evaluation-section"
        aria-labelledby="quality-heading"
      >
        <h2 id="quality-heading">Retrieval Quality</h2>
        {!results && (
          <p className="text-sm text-secondary">
            Evaluation is awaiting manual relevance judgments. Results will
            appear once the evaluation dataset is completed.
          </p>
        )}
        <div className="evaluation-table">
          <table aria-label="Retrieval quality at 10">
            <thead>
              <tr>
                <th scope="col">Metric</th>
                {modes.map((mode) => (
                  <th scope="col" key={mode}>
                    {labels[mode]}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {metrics.map(([label, key]) => (
                <tr key={key}>
                  <th scope="row">{label}</th>
                  {modes.map((mode) => {
                    const value = results?.metrics[mode][key];
                    return (
                      <td key={mode}>
                        {value == null ? "—" : value.toFixed(3)}
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
      <section
        className="surface evaluation-section"
        aria-labelledby="curve-heading"
      >
        <h2 id="curve-heading">Precision–Recall Curve</h2>
        {results?.curves.length ? (
          <MeasuredCurves points={results.curves} />
        ) : (
          <p className="text-sm text-secondary">
            {results
              ? "No query has known relevant papers, so precision–recall curves are undefined."
              : "Complete the relevance CSV to compare precision and pooled recall."}
          </p>
        )}
      </section>
      <section
        className="surface evaluation-section"
        aria-labelledby="methodology-heading"
      >
        <h2 id="methodology-heading">Evaluation Methodology</h2>
        <p>
          All four methods use the same five queries and manual CSV judgments: 0
          = irrelevant, 1 = partially relevant, 2 = highly relevant. Grades 1
          and 2 count as relevant. Blank means unjudged, never irrelevant.
        </p>
        <p>
          Precision@10 is the fraction of the top 10 papers that are relevant.
          Pooled Recall@10 is the fraction of relevant papers in the combined
          top-10 pool that are retrieved, not recall over the entire corpus.
        </p>
        <p>
          MAP@10 averages AP@10 across queries, rewarding relevant papers ranked
          earlier and dividing each AP by min(relevant papers, 10). nDCG@10 uses
          graded relevance and logarithmic rank discounts.
        </p>
      </section>
    </div>
  );
}
