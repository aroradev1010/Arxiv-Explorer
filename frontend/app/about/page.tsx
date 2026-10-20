import { SystemStatus } from "@/components/system-status";
export const metadata = { title: "About & methodology" };
export default function Page() {
  return (
    <div className="prose">
      <div className="page-heading">
        <div className="eyebrow">An information retrieval project</div>
        <h1>Research discovery, made transparent.</h1>
        <p>
          ArXiv Explorer searches a locally indexed subset of arXiv metadata. It
          is an independent academic project.
        </p>
      </div>
      <h2>The collection</h2>
      <p>
        The verified project dataset was built from 50,000 actual papers using
        deterministic sampling with seed 42. SQLite stores metadata and stable
        ArXiv identifiers. Live corpus counts and provenance are shown below;
        the collection is a subset of arXiv and does not provide exhaustive
        coverage.
      </p>
      <h2>Four retrieval perspectives</h2>
      <p>
        TF-IDF weights distinctive query terms. BM25 adds term saturation and
        document-length normalization. Semantic retrieval uses the existing
        all-MiniLM-L6-v2 Sentence Transformer embeddings and FAISS vector
        similarity. Hybrid retrieval combines the three native rankings with
        Reciprocal Rank Fusion: RRF(d) = Σ 1 / (k + rankᵢ(d)).
      </p>
      <h2>Architecture & filtering</h2>
      <p>
        A Next.js frontend sends typed requests to the FastAPI backend. Filters
        combine with AND and apply before top-K selection, including
        secondary-category membership. Author filters match name text and do not
        establish personal identity. SQLite, lexical indexes, and the existing
        embedding model remain owned by the backend.
      </p>
      <h2>Interpreting results</h2>
      <p>
        Scores are native algorithm values, not relevance probabilities, and
        cannot be directly compared across methods. Semantic similarity is a
        vector-space measure without a causal word-level explanation. Lexical
        explanations show matched indexed tokens, which may be stemmed.
      </p>
      <h2>Limits & reproducibility</h2>
      <p>
        Native methods expose a bounded ranking window of 1,000 by default;
        hybrid exposes 200. Candidate counts describe this window, not every
        relevant paper in the corpus. Query timings measure current service work
        and exclude network transport. Comparison method totals attribute shared
        work. Formal quality claims require relevance judgments and controlled
        benchmark runs.
      </p>
      <p>
        Abstracts retain their original text, including LaTeX. Mathematical
        expressions are displayed as text. Category names appear only where the
        dataset provides them.
      </p>
      <SystemStatus />
    </div>
  );
}
