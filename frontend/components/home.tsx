"use client";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  Network,
  TextSearch,
  ScanText,
  Layers,
  ArrowUpRight,
} from "lucide-react";
import { useStats } from "@/hooks/queries";
import { SearchForm } from "./search/search-form";
import { searchURL, labels, descriptions, modes } from "@/lib/state";
import { Button } from "./ui/button";
const icons = {
  hybrid: Layers,
  tfidf: TextSearch,
  bm25: ScanText,
  semantic: Network,
};
export function Home() {
  const router = useRouter();
  const stats = useStats();
  return (
    <>
      <section className="hero">
        <div className="eyebrow">
          Ideas are connected. Find the connections.
        </div>
        <h1>
          Explore Research.
          <br />
          <span>Discover Knowledge.</span>
        </h1>
        <p className="intro">
          Search and compare academic papers using traditional information
          retrieval, semantic search, and hybrid ranking.
        </p>
        <SearchForm
          onSubmit={(q, mode) =>
            router.push(searchURL({ q, mode, offset: 0, filters: {} }))
          }
        />
        <div className="suggestions">
          {[
            "Graph neural networks",
            "Quantum field theory",
            "Climate change prediction",
            "Reinforcement learning in robotics",
            "Medical image classification",
          ].map((q) => (
            <Link
              key={q}
              href={searchURL({ q, mode: "hybrid", offset: 0, filters: {} })}
            >
              {q} ↗
            </Link>
          ))}
        </div>
      </section>
      {stats.data ? (
        <section className="stats" aria-label="Corpus statistics">
          {[
            [stats.data.indexed_paper_count, "Indexed papers"],
            [
              stats.data.category_counts.categories.length,
              "Scientific categories",
            ],
            [stats.data.algorithms.length, "Retrieval algorithms"],
            [stats.data.embedding_dimension, "Embedding dimensions"],
          ].map(([value, name]) => (
            <div className="stat" key={name}>
              <strong>{Number(value).toLocaleString()}</strong>
              <span>{name}</span>
            </div>
          ))}
        </section>
      ) : (
        <div
          className="surface mb-10 p-6 text-center text-secondary"
          role="status"
        >
          {stats.isPending
            ? "Loading corpus statistics…"
            : "Corpus statistics are currently unavailable."}
          {stats.isError && (
            <Button variant="ghost" onClick={() => stats.refetch()}>
              Retry
            </Button>
          )}
        </div>
      )}
      <section>
        <div className="section-heading">
          <div>
            <div className="eyebrow mb-2">Four ways to discover</div>
            <h2>One collection. Different perspectives.</h2>
          </div>
          <Link href="/compare" className="text-sm text-primary">
            Compare methods <ArrowUpRight className="inline" size={15} />
          </Link>
        </div>
        <div className="methods">
          {modes.map((m) => {
            const Icon = icons[m];
            return (
              <div key={m} className="method surface">
                <Icon size={23} />
                <h3>{labels[m]}</h3>
                <p>
                  {descriptions[m]}.{" "}
                  {m === "hybrid"
                    ? "Combines lexical and semantic rankings."
                    : m === "semantic"
                      ? "Find related concepts beyond shared keywords."
                      : m === "bm25"
                        ? "Balances term frequency and document length."
                        : "Weights distinctive words across the corpus."}
                </p>
              </div>
            );
          })}
        </div>
        <div className="mt-8 text-sm text-secondary">
          Built for transparent research discovery.{" "}
          <Link href="/about" className="text-primary">
            Read the methodology →
          </Link>
        </div>
      </section>
    </>
  );
}
