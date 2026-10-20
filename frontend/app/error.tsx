"use client";
import { ErrorState } from "@/components/ui/states";
export default function ErrorPage({ retry }: { retry: () => void }) {
  return (
    <ErrorState
      error={new Error("Something went wrong while displaying this page.")}
      retry={retry}
    />
  );
}
