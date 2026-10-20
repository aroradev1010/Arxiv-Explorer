import { Suspense } from "react";
import { JudgeWorkspace } from "@/components/evaluation/judge";
export const metadata = { title: "Human relevance judgments" };
export default function Page() {
  return (
    <Suspense fallback={<p>Loading annotation workspace…</p>}>
      <JudgeWorkspace />
    </Suspense>
  );
}
