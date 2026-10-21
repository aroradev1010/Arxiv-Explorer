"use client";
import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
} from "recharts";
import { labels } from "@/lib/state";
import type { Mode } from "@/lib/api/types";
const modes = ["tfidf", "bm25", "semantic", "hybrid"] as const;
export interface CurvePoint {
  algorithm: Mode;
  rank: number;
  precision: number;
  pooled_recall: number | null;
}
export function MeasuredCurves({ points }: { points: CurvePoint[] }) {
  return (
    <div>
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
              label={{
                value: "Pooled recall",
                position: "insideBottom",
                offset: -5,
              }}
              height={40}
            />
            <YAxis
              domain={[0, 1]}
              name="Precision"
              label={{ value: "Precision", angle: -90, position: "insideLeft" }}
            />
            <Tooltip />
            <Legend />
            {modes.map((m, i) => (
              <Line
                key={m}
                name={labels[m]}
                data={points.filter(
                  (p) => p.algorithm === m && p.pooled_recall !== null,
                )}
                dataKey="precision"
                type="linear"
                stroke={["#9aaeff", "#5ed0b2", "#f5b46b", "#c7a0ff"][i]}
                isAnimationActive={false}
              />
            ))}
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
