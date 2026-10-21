import { readFile } from "node:fs/promises";
import { createHash } from "node:crypto";
import path from "node:path";
import { z } from "zod";
import type { EvaluationResults } from "@/components/evaluation/dashboard";

const modes = ["tfidf", "bm25", "semantic", "hybrid"] as const;
const value = z.number().finite().min(0).max(1);
const metric = z.object({
  precision: value.nullable(),
  pooled_recall: value.nullable(),
  ap: value.nullable(),
  ndcg: value.nullable(),
});
const completed = z.object({
  schema_version: z.literal(1),
  status: z.literal("complete"),
  cutoff: z.literal(10),
  query_count: z.number().int().positive(),
  judgment_count: z.number().int().positive(),
  judgments_sha256: z.string().regex(/^[a-f0-9]{64}$/),
  rankings_sha256: z.string().regex(/^[a-f0-9]{64}$/),
  metrics: z.object({
    tfidf: metric,
    bm25: metric,
    semantic: metric,
    hybrid: metric,
  }),
  curves: z.array(
    z.object({
      algorithm: z.enum(modes),
      rank: z.number().int().min(1).max(10),
      precision: value,
      pooled_recall: value,
    }),
  ),
});

// Server-only file access: refresh the page after running the evaluation command.
export async function readEvaluationResults(
  directory = path.resolve(process.cwd(), "..", "data", "evaluation"),
): Promise<EvaluationResults | undefined> {
  try {
    const parsed = completed.safeParse(
      JSON.parse(await readFile(path.join(directory, "results.json"), "utf8")),
    );
    if (!parsed.success) return undefined;
    const result = parsed.data;
    const [csv, rankings] = await Promise.all([
      readFile(path.join(directory, "relevance_judgments.csv")),
      readFile(path.join(directory, "rankings.json")),
    ]);
    const hash = (content: Buffer) =>
      createHash("sha256").update(content).digest("hex");
    if (
      hash(csv) !== result.judgments_sha256 ||
      hash(rankings) !== result.rankings_sha256
    )
      return undefined;
    const defined = modes.every(
      (mode) => result.metrics[mode].pooled_recall !== null,
    );
    if (defined) {
      if (result.curves.length !== 40) return undefined;
      for (const mode of modes) {
        const ranks = result.curves
          .filter((point) => point.algorithm === mode)
          .map((point) => point.rank);
        if (ranks.length !== 10 || new Set(ranks).size !== 10) return undefined;
      }
    } else if (
      result.curves.length ||
      modes.some((mode) => result.metrics[mode].pooled_recall !== null)
    ) {
      return undefined;
    }
    return { metrics: result.metrics, curves: result.curves };
  } catch {
    // Missing, incomplete, changed or malformed artifacts must never display scores.
    return undefined;
  }
}
