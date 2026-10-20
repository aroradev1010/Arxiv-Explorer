"use client";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api/client";
import { useStats } from "@/hooks/queries";
import { Button } from "./ui/button";
export function SystemStatus() {
  const stats = useStats();
  const live = useQuery({
    queryKey: ["health", "live"],
    queryFn: ({ signal }) => api.health("live", signal),
  });
  const ready = useQuery({
    queryKey: ["health", "ready"],
    queryFn: ({ signal }) => api.health("ready", signal),
  });
  return (
    <section className="surface p-6 mt-8">
      <h2>Live corpus & service</h2>
      <p className="mt-4">
        Process:{" "}
        {live.data?.status || (live.isPending ? "Checking…" : "Unavailable")} ·
        Search index:{" "}
        {ready.data?.status ||
          (ready.isPending ? "Checking…" : "Not ready or unavailable")}
      </p>
      {stats.data ? (
        <>
          <p>
            {stats.data.indexed_paper_count.toLocaleString()} indexed papers ·{" "}
            {stats.data.vocabulary_size.toLocaleString()} lexical features ·{" "}
            {stats.data.embedding_dimension} vector dimensions.
          </p>
          <p>Model: {stats.data.embedding_model}</p>
          <details>
            <summary>Inspect provenance</summary>
            <p className="break-all">
              Dataset SHA256: {stats.data.dataset_version}
              <br />
              Index SHA256: {stats.data.index_version}
              <br />
              Model revision: {stats.data.model_revision || "Unavailable"}
            </p>
          </details>
        </>
      ) : (
        <p>Dataset statistics are currently unavailable.</p>
      )}
      {(stats.isError || live.isError || ready.isError) && (
        <Button
          variant="outline"
          onClick={() => {
            stats.refetch();
            live.refetch();
            ready.refetch();
          }}
        >
          Retry service checks
        </Button>
      )}
    </section>
  );
}
