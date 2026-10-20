import Link from "next/link";
import { AlertCircle, Search } from "lucide-react";
import { Button } from "./button";
import { ApiError } from "@/lib/api/client";
export function ErrorState({
  error,
  retry,
}: {
  error: Error;
  retry?: () => void;
}) {
  return (
    <div role="alert" className="state">
      <AlertCircle className="mx-auto mb-3 text-primary" />
      <h2>
        {error instanceof ApiError && error.status === 404
          ? "Paper not found"
          : "Unable to load research"}
      </h2>
      <p>{error.message}</p>
      {retry && (
        <Button onClick={retry} variant="outline">
          Retry
        </Button>
      )}
      {error instanceof ApiError && error.status === 404 && (
        <Link href="/search">Back to search</Link>
      )}
    </div>
  );
}
export function EmptyState({
  title = "No papers found",
  description = "Try a broader query or clear your filters.",
}: {
  title?: string;
  description?: string;
}) {
  return (
    <div className="state">
      <Search className="mx-auto mb-3 text-secondary" />
      <h2>{title}</h2>
      <p>{description}</p>
    </div>
  );
}
export function LoadingSkeleton() {
  return (
    <div role="status" aria-label="Loading research" className="space-y-4">
      {[0, 1, 2].map((i) => (
        <div key={i} className="surface animate-pulse p-6">
          <div className="mb-4 h-5 w-3/4 rounded bg-muted" />
          <div className="mb-3 h-3 w-1/2 rounded bg-muted" />
          <div className="h-16 rounded bg-muted" />
        </div>
      ))}
    </div>
  );
}
