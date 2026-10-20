"use client";
import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  BarChart,
  Bar,
  Legend,
} from "recharts";
import { EmptyState } from "../ui/states";
import { Button } from "../ui/button";
function DownloadChart({ name }: { name: string }) {
  return (
    <Button
      variant="outline"
      onClick={(e) => {
        const svg = e.currentTarget
          .closest("[data-chart]")
          ?.querySelector("svg.recharts-surface");
        if (!svg) return;
        const clone = svg.cloneNode(true) as SVGElement;
        clone.setAttribute("xmlns", "http://www.w3.org/2000/svg");
        const blob = new Blob([new XMLSerializer().serializeToString(clone)], {
          type: "image/svg+xml",
        });
        const url = URL.createObjectURL(blob);
        const link = document.createElement("a");
        link.href = url;
        link.download = name + ".svg";
        link.click();
        setTimeout(() => URL.revokeObjectURL(url), 1000);
      }}
    >
      Download {name} SVG
    </Button>
  );
}
export interface PrecisionRecallPoint {
  recall: number;
  tfidf?: number;
  bm25?: number;
  semantic?: number;
  hybrid?: number;
}
export function MeasuredCurves({
  points,
}: {
  points: {
    algorithm: string;
    rank: number;
    precision: number;
    pooled_recall: number | null;
  }[];
}) {
  if (!points.length)
    return (
      <EmptyState
        title="Precision–recall curve pending"
        description="Complete human judgments with known relevant papers are required."
      />
    );
  return (
    <div data-chart>
      <div
        role="img"
        aria-label="Uninterpolated precision versus pooled recall by algorithm"
      >
        <ResponsiveContainer width="100%" height={320}>
          <LineChart>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis
              dataKey="pooled_recall"
              type="number"
              domain={[0, 1]}
              name="Pooled recall"
            />
            <YAxis domain={[0, 1]} name="Precision" />
            <Tooltip />
            <Legend />
            {["tfidf", "bm25", "semantic", "hybrid"].map((m, i) => (
              <Line
                key={m}
                name={m}
                data={points.filter((p) => p.algorithm === m)}
                dataKey="precision"
                type="linear"
                stroke={["#374ec5", "#137c68", "#a04c14", "#7856ac"][i]}
                isAnimationActive={false}
              />
            ))}
          </LineChart>
        </ResponsiveContainer>
      </div>
      <DownloadChart name="precision-recall" />
    </div>
  );
}
export function PrecisionRecallChart({
  data,
}: {
  data: PrecisionRecallPoint[];
}) {
  if (!data.length)
    return (
      <EmptyState
        title="Precision–recall curve pending"
        description="Human relevance judgments are required."
      />
    );
  return (
    <div role="img" aria-label="Precision versus recall by algorithm">
      <ResponsiveContainer width="100%" height={320}>
        <LineChart data={data}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey="recall" domain={[0, 1]} type="number" />
          <YAxis domain={[0, 1]} />
          <Tooltip />
          <Legend />
          {(["tfidf", "bm25", "semantic", "hybrid"] as const).map((m, i) => (
            <Line
              key={m}
              dataKey={m}
              stroke={["#374ec5", "#137c68", "#a04c14", "#7856ac"][i]}
              connectNulls={false}
            />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
export function LatencyChart({
  data,
}: {
  data: { method: string; milliseconds: number }[];
}) {
  if (!data.length)
    return (
      <EmptyState
        title="Performance benchmarks pending"
        description="Warmup and repeated measured runs are required."
      />
    );
  return (
    <div data-chart>
      <div role="img" aria-label="Measured algorithm latency in milliseconds">
        <ResponsiveContainer width="100%" height={300}>
          <BarChart data={data}>
            <XAxis dataKey="method" />
            <YAxis unit=" ms" />
            <Tooltip />
            <Bar dataKey="milliseconds" fill="#374ec5" />
          </BarChart>
        </ResponsiveContainer>
      </div>
      <DownloadChart name="latency" />
    </div>
  );
}
