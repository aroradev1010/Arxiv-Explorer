"use client";
import { useState } from "react";
import Link from "next/link";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { evaluationApi, type EvaluationQuery } from "@/lib/api/evaluation";
import { Button } from "@/components/ui/button";
import { ErrorState, EmptyState } from "@/components/ui/states";
import { LatencyChart, MeasuredCurves } from "./charts";

const active = (status: string) => ["QUEUED", "RUNNING"].includes(status);
const metricValue = (value: number | null | undefined) =>
  value == null ? "Unavailable" : value.toFixed(4);

export function EvaluationWorkspace() {
  const cache = useQueryClient();
  const [poolChoice, setPool] = useState("");
  const [runChoice, setRun] = useState("");
  const [benchmarkChoice, setBenchmark] = useState("");
  const [analysisQuery, setAnalysisQuery] = useState("");
  const [version, setVersion] = useState("");
  const [depth, setDepth] = useState(10);
  const [cutoff, setCutoff] = useState(10);
  const [threshold, setThreshold] = useState(1);
  const [warmups, setWarmups] = useState(2);
  const [iterations, setIterations] = useState(10);
  const [filters, setFilters] = useState("{}");
  const [editor, setEditor] = useState<string | null>(null);
  const [editError, setEditError] = useState("");
  const queries = useQuery({
    queryKey: ["evaluation", "queries", version],
    queryFn: ({ signal }) =>
      evaluationApi.queries(signal, version || undefined),
  });
  const config = useQuery({
    queryKey: ["evaluation", "config"],
    queryFn: ({ signal }) => evaluationApi.config(signal),
  });
  const pools = useQuery({
    queryKey: ["evaluation", "pools"],
    queryFn: ({ signal }) => evaluationApi.pools(signal),
    refetchInterval: (q) =>
      q.state.data?.some((p) => active(p.status)) ? 1000 : false,
  });
  const runs = useQuery({
    queryKey: ["evaluation", "runs"],
    queryFn: ({ signal }) => evaluationApi.runs(signal),
  });
  const benchmarks = useQuery({
    queryKey: ["evaluation", "benchmarks"],
    queryFn: ({ signal }) => evaluationApi.benchmarks(signal),
    refetchInterval: (q) =>
      q.state.data?.some((b) => active(b.status)) ? 1000 : false,
  });
  const poolId = poolChoice || pools.data?.[0]?.id || "";
  const runId = runChoice || runs.data?.[0]?.id || "";
  const benchId = benchmarkChoice || benchmarks.data?.[0]?.id || "";
  const pool = pools.data?.find((p) => p.id === poolId);
  const benchmark = benchmarks.data?.find((b) => b.id === benchId);
  const progress = useQuery({
    queryKey: ["evaluation", "progress", poolId, cutoff, threshold],
    queryFn: ({ signal }) =>
      evaluationApi.progress(poolId, signal, cutoff, threshold),
    enabled: !!poolId,
    refetchInterval: pool && active(pool.status) ? 1000 : false,
  });
  const run = useQuery({
    queryKey: ["evaluation", "run", runId],
    queryFn: ({ signal }) => evaluationApi.run(runId, signal),
    enabled: !!runId,
  });
  const curves = useQuery({
    queryKey: ["evaluation", "curves", runId],
    queryFn: ({ signal }) => evaluationApi.curves(runId, signal),
    enabled: !!runId,
  });
  const refresh = () => cache.invalidateQueries({ queryKey: ["evaluation"] });
  const createPool = useMutation({
    mutationFn: () =>
      evaluationApi.createPool({
        query_set_version: queries.data?.version,
        depth,
        filters: JSON.parse(filters),
      }),
    onSuccess: (p) => {
      setPool(p.id);
      refresh();
    },
  });
  const createRun = useMutation({
    mutationFn: () =>
      evaluationApi.createRun({
        pool_id: poolId,
        cutoff,
        relevance_threshold: threshold,
      }),
    onSuccess: (r) => {
      setRun(r.id);
      refresh();
    },
  });
  const createBenchmark = useMutation({
    mutationFn: () =>
      evaluationApi.createBenchmark({
        query_set_version: queries.data?.version,
        depth,
        filters: JSON.parse(filters),
        warmup_iterations: warmups,
        measured_iterations: iterations,
      }),
    onSuccess: (b) => {
      setBenchmark(b.id);
      refresh();
    },
  });
  const saveQueries = useMutation({
    mutationFn: (q: EvaluationQuery[]) => evaluationApi.saveQueries(q),
    onSuccess: (c) => {
      setEditor(null);
      setVersion(c.version);
      refresh();
    },
  });
  const mutations = config.data?.mutations_enabled === true;
  const error =
    queries.error ||
    config.error ||
    pools.error ||
    runs.error ||
    benchmarks.error ||
    progress.error ||
    run.error ||
    curves.error ||
    createPool.error ||
    createRun.error ||
    createBenchmark.error ||
    saveQueries.error;
  return (
    <>
      <div className="page-heading">
        <div className="eyebrow">Research workspace · Phase 5</div>
        <h1>Evaluate what matters.</h1>
        <p>Frozen rankings, human judgments, and reproducible comparisons.</p>
      </div>
      {error ? <ErrorState error={error} retry={refresh} /> : null}
      {queries.isPending ? (
        <p role="status">Loading evaluation workspace…</p>
      ) : null}
      {!mutations ? (
        <p className="state">
          Read-only workspace. Enable EVALUATION_MUTATIONS_ENABLED on the local
          backend to create experiments and save judgments.
        </p>
      ) : null}
      <div className="metric-grid mb-8">
        {[
          ["Information needs", queries.data?.queries.length ?? 0],
          ["Judgments saved", progress.data?.judged ?? 0],
          ["Eligible queries", progress.data?.eligible_queries ?? 0],
          ["Evaluation runs", runs.data?.length ?? 0],
        ].map(([label, v]) => (
          <div className="surface" key={label}>
            <p>{label}</p>
            <strong className="text-3xl">{v}</strong>
          </div>
        ))}
      </div>
      <section className="surface evaluation-section">
        <h2>1. Review the query collection</h2>
        <label>
          Query set version
          <select
            aria-label="Query set version"
            value={queries.data?.version || ""}
            onChange={(e) => setVersion(e.target.value)}
          >
            {queries.data?.versions.map((v) => (
              <option key={v.version} value={v.version}>
                {v.version}
              </option>
            ))}
          </select>
        </label>
        <p>
          {queries.data?.queries.length ?? 0} proposed information needs. Review
          domains and descriptions before finalizing.
        </p>
        <div className="evaluation-actions">
          <Button
            disabled={!mutations || !queries.data}
            onClick={() =>
              setEditor(JSON.stringify(queries.data?.queries, null, 2))
            }
          >
            Review / edit / add queries
          </Button>
          <a
            href={evaluationApi.exportUrl(
              "queries",
              queries.data?.version,
              "json",
            )}
          >
            Export queries JSON
          </a>
          <a
            href={evaluationApi.exportUrl(
              "queries",
              queries.data?.version,
              "csv",
            )}
          >
            Export queries CSV
          </a>
          <a
            href={evaluationApi.exportUrl("report", poolId || undefined, "md")}
          >
            Export methodology / status report
          </a>
        </div>
        {editor !== null ? (
          <div>
            <label>
              Query collection JSON
              <textarea
                rows={16}
                value={editor}
                onChange={(e) => setEditor(e.target.value)}
              />
            </label>
            <p>
              Import by pasting a query array or an exported object with a
              queries field. Saving creates a version; prior pools keep their
              definitions.
            </p>
            <div className="evaluation-actions">
              <Button
                disabled={saveQueries.isPending}
                onClick={() => {
                  try {
                    const parsed = JSON.parse(editor);
                    saveQueries.mutate(
                      Array.isArray(parsed) ? parsed : parsed.queries,
                    );
                    setEditError("");
                  } catch {
                    setEditError("Enter valid query collection JSON.");
                  }
                }}
              >
                Save query version
              </Button>
              <Button
                variant="outline"
                onClick={() => {
                  if (window.confirm("Discard query edits?")) setEditor(null);
                }}
              >
                Cancel
              </Button>
            </div>
            {editError ? <p role="alert">{editError}</p> : null}
          </div>
        ) : (
          <details>
            <summary>Read query definitions</summary>
            {queries.data?.queries.map((q) => (
              <article key={q.id} className="py-3">
                <h3>
                  {q.id} · {q.query}
                </h3>
                <p>{q.information_need}</p>
                <p className="text-sm text-secondary">
                  {q.domain} · {q.query_type}
                </p>
              </article>
            ))}
          </details>
        )}
      </section>
      <section className="surface evaluation-section">
        <h2>2. Generate a frozen candidate pool</h2>
        <p>
          All four methods use the same queries and filters. At most{" "}
          {(queries.data?.queries.length ?? 0) * 4 * depth} candidate pairs
          before deduplication.
        </p>
        <div className="evaluation-actions">
          <label>
            Pool depth
            <input
              type="number"
              min={1}
              max={100}
              value={depth}
              onChange={(e) => setDepth(Number(e.target.value))}
            />
          </label>
          <label>
            Search filters JSON
            <input
              value={filters}
              onChange={(e) => setFilters(e.target.value)}
            />
          </label>
          <Button
            disabled={
              !mutations ||
              createPool.isPending ||
              pools.data?.some((p) => active(p.status)) ||
              benchmarks.data?.some((b) => active(b.status))
            }
            onClick={() => createPool.mutate()}
          >
            Generate pool
          </Button>
        </div>
        <label>
          Candidate pool
          <select
            value={poolId}
            onChange={(e) => setPool(e.target.value)}
            aria-label="Candidate pool"
          >
            <option value="">Choose a pool</option>
            {pools.data?.map((p) => (
              <option key={p.id} value={p.id}>
                {p.id} · {p.status} · {p.candidate_count} pairs
              </option>
            ))}
          </select>
        </label>
        {pool ? (
          <>
            <p role="status">
              {pool.status}
              {pool.stale ? " · STALE" : ""} · {pool.candidate_count} unique
              pairs{pool.error ? " · " + pool.error : ""}
            </p>
            <p>
              {pool.metadata.query_set_version} · depth {pool.metadata.depth}
            </p>
          </>
        ) : (
          <EmptyState
            title="No candidate pools yet"
            description="Generate a pool before beginning human annotation."
          />
        )}
      </section>
      <section className="surface evaluation-section">
        <h2>3. Judge papers and check readiness</h2>
        <p>
          Grades: 0 not relevant, 1 partially relevant, 2 highly relevant.
          Unjudged remains distinct.
        </p>
        {pool && pool.status === "COMPLETED" ? (
          <Link href={`/evaluation/judge?pool=${poolId}`}>
            Open blind annotation workspace →
          </Link>
        ) : null}
        {progress.data ? (
          <>
            <p>
              {progress.data.judged} judged / {progress.data.total} pooled pairs
              · {progress.data.unjudged} unjudged ·{" "}
              {progress.data.missing_required} required judgments remain for the
              top-{cutoff} union.
            </p>
            <div className="table-scroll">
              <table>
                <thead>
                  <tr>
                    <th>Query</th>
                    <th>Judged</th>
                    <th>Missing required</th>
                    <th>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {progress.data.queries.map((q) => (
                    <tr key={q.query_id}>
                      <td>{q.query_id}</td>
                      <td>
                        {q.judged}/{q.total}
                      </td>
                      <td>{q.missing_required}</td>
                      <td>{q.status}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        ) : null}
      </section>
      <section className="surface evaluation-section">
        <h2>4. Run an effectiveness experiment</h2>
        <p>
          Only queries with complete four-method top-K coverage enter the
          comparison. Recall is relative to known relevant papers in the judged
          pool.
        </p>
        <div className="evaluation-actions">
          <label>
            Cutoff K
            <input
              type="number"
              min={1}
              max={100}
              value={cutoff}
              onChange={(e) => setCutoff(Number(e.target.value))}
            />
          </label>
          <label>
            Binary relevance threshold
            <select
              value={threshold}
              onChange={(e) => setThreshold(Number(e.target.value))}
            >
              <option value={1}>Grade ≥ 1</option>
              <option value={2}>Grade ≥ 2</option>
            </select>
          </label>
          <Button
            disabled={
              !mutations ||
              !progress.data?.eligible_queries ||
              pool?.stale ||
              createRun.isPending
            }
            onClick={() => createRun.mutate()}
          >
            Run evaluation
          </Button>
        </div>
        <label>
          Evaluation run
          <select
            value={runId}
            onChange={(e) => setRun(e.target.value)}
            aria-label="Evaluation run"
          >
            <option value="">Choose a run</option>
            {runs.data?.map((r) => (
              <option key={r.id} value={r.id}>
                {r.id} · {r.created_at}
              </option>
            ))}
          </select>
        </label>
        {run.data ? (
          <>
            <p>
              {run.data.status}
              {run.data.stale
                ? " · STALE: historical results use older assets/configuration"
                : ""}{" "}
              · {run.data.metadata.eligible_queries.length} included /{" "}
              {run.data.metadata.excluded_queries.length} excluded queries ·
              threshold {run.data.metadata.relevance_threshold} · K=
              {run.data.metadata.cutoff}
            </p>
            <div className="table-scroll">
              <table>
                <caption>
                  Mean effectiveness over the same eligible queries (undefined
                  metrics excluded)
                </caption>
                <thead>
                  <tr>
                    <th>Method</th>
                    <th>P@{run.data.metadata.cutoff}</th>
                    <th>Pooled Recall@{run.data.metadata.cutoff}</th>
                    <th>MAP@{run.data.metadata.cutoff}</th>
                    <th>nDCG@{run.data.metadata.cutoff}</th>
                  </tr>
                </thead>
                <tbody>
                  {Object.entries(run.data.metadata.aggregate).map(([m, v]) => (
                    <tr key={m}>
                      <th>{m}</th>
                      <td>{metricValue(v.precision)}</td>
                      <td>{metricValue(v.pooled_recall)}</td>
                      <td>{metricValue(v.ap)}</td>
                      <td>{metricValue(v.ndcg)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="metric-grid my-6">
              {(["precision", "pooled_recall", "ap", "ndcg"] as const).map(
                (metric, i) => (
                  <div className="surface" key={metric}>
                    <h3>
                      {["Precision", "Pooled Recall", "MAP", "nDCG"][i]}@
                      {run.data!.metadata.cutoff}
                    </h3>
                    {Object.entries(run.data!.metadata.aggregate).map(
                      ([method, v]) => (
                        <p key={method}>
                          {method}: {metricValue(v[metric])}
                        </p>
                      ),
                    )}
                  </div>
                ),
              )}
            </div>
            <label>
              Curve / analysis query
              <select
                value={analysisQuery}
                onChange={(e) => setAnalysisQuery(e.target.value)}
              >
                <option value="">Aggregate over eligible queries</option>
                {run.data.metadata.eligible_queries.map((id) => (
                  <option key={id} value={id}>
                    {id}
                  </option>
                ))}
              </select>
            </label>
            <MeasuredCurves
              points={
                (analysisQuery
                  ? curves.data?.points.filter(
                      (p) =>
                        p.query_id === analysisQuery &&
                        p.pooled_recall !== null,
                    )
                  : curves.data?.aggregate) ?? []
              }
            />
            <p>{curves.data?.convention}</p>
            <details>
              <summary>Per-query analysis and ranking differences</summary>
              <div className="table-scroll">
                <table>
                  <thead>
                    <tr>
                      <th>Query</th>
                      <th>Method</th>
                      <th>Precision</th>
                      <th>Pooled recall</th>
                      <th>AP</th>
                      <th>nDCG</th>
                      <th>Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {run.data.metrics
                      ?.filter(
                        (m) => !analysisQuery || m.query_id === analysisQuery,
                      )
                      .map((m) => (
                        <tr key={m.query_id + m.algorithm}>
                          <td>{m.query_id}</td>
                          <td>{m.algorithm}</td>
                          <td>{metricValue(m.precision)}</td>
                          <td>{metricValue(m.pooled_recall)}</td>
                          <td>{metricValue(m.ap)}</td>
                          <td>{metricValue(m.ndcg)}</td>
                          <td>{m.status}</td>
                        </tr>
                      ))}
                  </tbody>
                </table>
              </div>
              <p>
                Frozen rankings and native scores are available in the run JSON
                export. Included-query counts and metric variation are preserved
                in the aggregate export. Per-query variation does not establish
                statistical significance.
              </p>
              <h3>
                Frozen rankings for{" "}
                {analysisQuery || run.data.metadata.eligible_queries[0]}
              </h3>
              <div className="table-scroll">
                <table>
                  <thead>
                    <tr>
                      <th>Method</th>
                      <th>Rank</th>
                      <th>Paper</th>
                      <th>Native score</th>
                      <th>Snapshot grade</th>
                    </tr>
                  </thead>
                  <tbody>
                    {run.data.rankings
                      ?.filter(
                        (r) =>
                          r.query_id ===
                            (analysisQuery ||
                              run.data!.metadata.eligible_queries[0]) &&
                          r.rank <= run.data!.metadata.cutoff,
                      )
                      .map((r) => (
                        <tr key={r.algorithm + r.rank}>
                          <td>{r.algorithm}</td>
                          <td>{r.rank}</td>
                          <td>
                            <Link
                              href={
                                "/papers?arxiv_id=" +
                                encodeURIComponent(r.paper_id)
                              }
                            >
                              {r.paper_id}
                            </Link>
                          </td>
                          <td>{r.native_score.toFixed(6)}</td>
                          <td>
                            {run.data!.judgment_snapshot?.[r.query_id]?.[
                              r.paper_id
                            ] ?? "Unjudged"}
                          </td>
                        </tr>
                      ))}
                  </tbody>
                </table>
              </div>
            </details>
            <div className="evaluation-actions">
              {["run", "metrics", "aggregate", "curves", "report"].map(
                (kind) => (
                  <a
                    key={kind}
                    href={evaluationApi.exportUrl(
                      kind,
                      runId,
                      kind === "report"
                        ? "md"
                        : kind === "run"
                          ? "json"
                          : "csv",
                    )}
                  >
                    Export {kind}
                  </a>
                ),
              )}
            </div>
          </>
        ) : (
          <EmptyState
            title="Retrieval evaluation is not available yet."
            description="Relevance judgments and benchmark runs are required before quality metrics can be displayed."
          />
        )}
      </section>
      <section className="surface evaluation-section">
        <h2>5. Measure repeated latency</h2>
        <p>
          Independent service-level searches, warmup first, deterministic
          randomized order, one benchmark job at a time. Avoid other heavy
          workloads.
        </p>
        <div className="evaluation-actions">
          <label>
            Warmup rounds
            <input
              type="number"
              min={0}
              max={10}
              value={warmups}
              onChange={(e) => setWarmups(Number(e.target.value))}
            />
          </label>
          <label>
            Measured rounds
            <input
              type="number"
              min={1}
              max={30}
              value={iterations}
              onChange={(e) => setIterations(Number(e.target.value))}
            />
          </label>
          <Button
            disabled={
              !mutations ||
              createBenchmark.isPending ||
              benchmarks.data?.some((b) => active(b.status)) ||
              pools.data?.some((p) => active(p.status))
            }
            onClick={() => createBenchmark.mutate()}
          >
            Start benchmark
          </Button>
        </div>
        <label>
          Benchmark run
          <select
            value={benchId}
            onChange={(e) => setBenchmark(e.target.value)}
          >
            <option value="">Choose a benchmark</option>
            {benchmarks.data?.map((b) => (
              <option key={b.id} value={b.id}>
                {b.id} · {b.status}
              </option>
            ))}
          </select>
        </label>
        {benchmark ? (
          <>
            <p role="status">
              {benchmark.status} · {benchmark.completed_samples}/
              {benchmark.metadata.total_samples} executions ·{" "}
              {benchmark.failed_samples} failed
              {benchmark.error ? " · " + benchmark.error : ""}
            </p>
            <LatencyChart
              data={Object.entries(benchmark.summary)
                .filter(([, s]) => s.mean !== null)
                .map(([method, s]) => ({ method, milliseconds: s.mean! }))}
            />
            <div className="table-scroll">
              <table>
                <thead>
                  <tr>
                    <th>Method</th>
                    <th>Samples</th>
                    <th>Mean ms</th>
                    <th>P50 ms</th>
                    <th>P95 ms</th>
                    <th>Min ms</th>
                    <th>Max ms</th>
                    <th>σ ms</th>
                  </tr>
                </thead>
                <tbody>
                  {Object.entries(benchmark.summary).map(([m, s]) => (
                    <tr key={m}>
                      <th>{m}</th>
                      <td>{s.count}</td>
                      {[
                        s.mean,
                        s.p50,
                        s.p95,
                        s.minimum,
                        s.maximum,
                        s.stddev,
                      ].map((v, i) => (
                        <td key={i}>{metricValue(v)}</td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <details>
              <summary>Measurement environment</summary>
              <pre className="overflow-auto">
                {JSON.stringify(benchmark.metadata.environment, null, 2)}
              </pre>
            </details>
            <div className="evaluation-actions">
              <a href={evaluationApi.exportUrl("benchmark", benchId, "csv")}>
                Export measured and warmup samples CSV
              </a>
              <a href={evaluationApi.exportUrl("benchmark", benchId)}>
                Export benchmark JSON
              </a>
            </div>
          </>
        ) : (
          <LatencyChart data={[]} />
        )}
      </section>
    </>
  );
}
