import { EvaluationDashboard } from "@/components/evaluation/dashboard";
import { readEvaluationResults } from "@/lib/evaluation-results";
import { connection } from "next/server";
export const metadata = { title: "Search Evaluation" };
export default async function Page() {
  await connection();
  return <EvaluationDashboard results={await readEvaluationResults()} />;
}
