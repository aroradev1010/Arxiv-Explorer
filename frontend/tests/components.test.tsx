import { it, expect, vi } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { SearchForm, ModeSelector } from "@/components/search/search-form";
import { FilterForm } from "@/components/search/filters";
import { PaperCard } from "@/components/papers/paper-card";
import { PaperPage, SimilarPapers } from "@/components/papers/paper-page";
import { ComparisonResults } from "@/components/comparison/compare-page";
import { EmptyState, ErrorState } from "@/components/ui/states";
import { ApiError } from "@/lib/api/client";
import type { RankedPaper, CompareResponse } from "@/lib/api/types";
import hybrid from "./fixtures/hybrid.json";
import categories from "./fixtures/categories.json";
import comparison from "./fixtures/compare.json";
import paper from "./fixtures/paper.json";
import similar from "./fixtures/similar.json";
vi.mock("next/navigation", () => ({
  useSearchParams: () => new URLSearchParams({ arxiv_id: paper.id }),
}));
function wrap(ui: React.ReactNode) {
  return render(
    <QueryClientProvider
      client={
        new QueryClient({ defaultOptions: { queries: { retry: false } } })
      }
    >
      {ui}
    </QueryClientProvider>,
  );
}
it("submits query on Enter and changes the retrieval method", async () => {
  const submit = vi.fn();
  const user = userEvent.setup();
  render(<SearchForm onSubmit={submit} />);
  await user.type(screen.getByLabelText("Research query"), "quantum fields");
  await user.click(screen.getByRole("button", { name: "BM25" }));
  await user.type(screen.getByLabelText("Research query"), "{Enter}");
  await waitFor(() =>
    expect(submit).toHaveBeenCalledWith("quantum fields", "bm25"),
  );
});
it("rejects punctuation and whitespace-only searches", async () => {
  const submit = vi.fn();
  const user = userEvent.setup();
  render(<SearchForm onSubmit={submit} />);
  await user.type(screen.getByLabelText("Research query"), "+++");
  await user.click(screen.getByRole("button", { name: "Search" }));
  expect(await screen.findByRole("alert")).toHaveTextContent(
    "letter or number",
  );
  expect(submit).not.toHaveBeenCalled();
});
it("mode selector communicates and activates choice", async () => {
  const change = vi.fn();
  render(<ModeSelector mode="hybrid" onChange={change} />);
  expect(screen.getByRole("button", { name: "Hybrid" })).toHaveAttribute(
    "aria-pressed",
    "true",
  );
  await userEvent.click(screen.getByRole("button", { name: "Semantic" }));
  expect(change).toHaveBeenCalledWith("semantic");
});
it("validates filters before applying and supports clear", async () => {
  vi.spyOn(globalThis, "fetch").mockResolvedValue(
    new Response(JSON.stringify(categories)),
  );
  const apply = vi.fn(),
    clear = vi.fn();
  const user = userEvent.setup();
  wrap(<FilterForm filters={{}} onApply={apply} onClear={clear} />);
  await screen.findByRole("option", { name: /cs.LG/ });
  await user.selectOptions(screen.getByLabelText("Category"), "cs.LG");
  await user.type(screen.getByLabelText("From year"), "2025");
  await user.type(screen.getByLabelText("To year"), "2000");
  await user.click(screen.getByRole("button", { name: "Apply filters" }));
  expect(screen.getByRole("alert")).toHaveTextContent("From year");
  expect(apply).not.toHaveBeenCalled();
  await user.clear(screen.getByLabelText("To year"));
  await user.type(screen.getByLabelText("To year"), "2025");
  await user.click(screen.getByRole("button", { name: "Apply filters" }));
  expect(apply).toHaveBeenCalledWith({
    category: "cs.LG",
    year_from: 2025,
    year_to: 2025,
  });
  await user.click(screen.getByRole("button", { name: "Clear filters" }));
  expect(clear).toHaveBeenCalled();
});
it("renders actual result metadata, safe links, abstract and RRF contributions", async () => {
  render(<PaperCard result={hybrid.results[0] as RankedPaper} />);
  expect(screen.getByRole("heading")).toHaveTextContent(
    hybrid.results[0].paper.title.replace(/\s+/g, " ").trim(),
  );
  expect(screen.getByRole("link", { name: "Open PDF ↗" })).toHaveAttribute(
    "href",
    "https://arxiv.org/pdf/" + hybrid.results[0].paper.id,
  );
  await userEvent.click(
    screen.getByRole("button", { name: "Expand abstract" }),
  );
  expect(
    screen.getByRole("button", { name: "Collapse abstract" }),
  ).toHaveAttribute("aria-expanded", "true");
  await userEvent.click(screen.getByText("Explore RRF contributions"));
  expect(screen.getByText(/Contributions agree/)).toBeVisible();
});
it("preserves legacy IDs and raw authors without unsafe HTML", () => {
  const r = structuredClone(hybrid.results[0]) as RankedPaper;
  r.paper.id = "hep-th/9901001";
  r.paper.authors = [];
  r.paper.authors_text = "Test Raw Collaboration";
  r.paper.title = "<script>test metadata</script>";
  render(<PaperCard result={r} />);
  expect(screen.getByText(/Test Raw Collaboration/)).toBeVisible();
  expect(screen.getByRole("link", { name: r.paper.title })).toHaveAttribute(
    "href",
    "/papers?arxiv_id=hep-th%2F9901001",
  );
  expect(document.querySelector("script")).toBeNull();
});
it("renders details while recommendation failure stays independent", async () => {
  vi.spyOn(globalThis, "fetch").mockImplementation(async (input) =>
    String(input).includes("/similar")
      ? new Response(
          JSON.stringify({
            error: {
              code: "not_ready",
              message: "Recommendations unavailable",
            },
          }),
          { status: 503 },
        )
      : new Response(JSON.stringify(paper)),
  );
  wrap(<PaperPage />);
  expect(
    await screen.findByRole("heading", {
      name: paper.title.replace(/\s+/g, " ").trim(),
    }),
  ).toBeVisible();
  expect(await screen.findByRole("alert")).toHaveTextContent(
    "Recommendations unavailable",
  );
  expect(
    screen.getByText(paper.abstract.replace(/\s+/g, " ").trim()),
  ).toBeVisible();
});
it("recommendations exclude the source and retain similarity labels", async () => {
  vi.spyOn(globalThis, "fetch").mockResolvedValue(
    new Response(
      JSON.stringify({
        ...similar,
        results: [hybrid.results[0], ...similar.results],
      }),
    ),
  );
  wrap(<SimilarPapers id={paper.id} />);
  await screen.findByRole("heading", {
    name: similar.results[0].paper.title.replace(/\s+/g, " ").trim(),
  });
  expect(
    screen.queryByRole("heading", {
      name: paper.title.replace(/\s+/g, " ").trim(),
    }),
  ).toBeNull();
  expect(screen.getAllByText("Cosine similarity").length).toBe(5);
});
it("comparison uses actual ranks, overlap and explanations", () => {
  render(<ComparisonResults data={comparison as CompareResponse} />);
  const table = screen
    .getAllByRole("table")
    .find((t) => within(t).queryByText("Δ BM25 → Hybrid"));
  expect(table).toBeDefined();
  expect(within(table!).getAllByRole("row").length).toBe(
    comparison.rank_differences.length + 1,
  );
  expect(screen.getByText("Ranking overlap")).toBeVisible();
});
it("empty and API error states expose actionable messages", async () => {
  const retry = vi.fn();
  render(
    <>
      <EmptyState />
      <ErrorState
        error={new ApiError(503, "not_ready", "Index not ready")}
        retry={retry}
      />
    </>,
  );
  expect(screen.getByText("No papers found")).toBeVisible();
  await userEvent.click(screen.getByRole("button", { name: "Retry" }));
  expect(retry).toHaveBeenCalledOnce();
});
