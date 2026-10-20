import { it, expect, vi } from "vitest";
import {
  render,
  screen,
  waitFor,
  fireEvent,
  within,
} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { JudgmentCard } from "@/components/evaluation/judge";
import { EvaluationWorkspace } from "@/components/evaluation/workspace";
import { evaluationApi } from "@/lib/api/evaluation";
import {
  documentFixture,
  collection,
  progressFixture,
  poolFixture,
  runFixture,
} from "./evaluation-fixtures";

function wrap(ui: React.ReactNode) {
  return render(
    <QueryClientProvider
      client={
        new QueryClient({
          defaultOptions: {
            queries: { retry: false },
            mutations: { retry: false },
          },
        })
      }
    >
      {ui}
    </QueryClientProvider>,
  );
}
it("saves a keyboard grade and only acknowledges persisted success", async () => {
  const save = vi
    .spyOn(evaluationApi, "judge")
    .mockResolvedValue({
      saved: true,
      query_id: "Q001",
      paper_id: documentFixture.paper_id,
      relevance_grade: 2,
    });
  const onSaved = vi.fn();
  const dirty = vi.fn();
  wrap(
    <JudgmentCard
      document={documentFixture}
      poolId="pool-fixture"
      writable
      onDirty={dirty}
      onSaved={onSaved}
    />,
  );
  fireEvent.keyDown(window, { key: "2" });
  expect(screen.getByLabelText("Highly relevant (2)")).toBeChecked();
  await userEvent.click(screen.getByRole("button", { name: "Save judgment" }));
  await screen.findByText("Judgment saved.");
  expect(save).toHaveBeenCalledWith(
    "pool-fixture",
    "Q001",
    documentFixture.paper_id,
    2,
  );
  expect(onSaved).toHaveBeenCalledOnce();
  expect(dirty).toHaveBeenCalledWith(true);
});
it("keeps unjudged separate and supports clearing a grade", async () => {
  const save = vi
    .spyOn(evaluationApi, "judge")
    .mockResolvedValue({
      saved: true,
      query_id: "Q001",
      paper_id: documentFixture.paper_id,
      relevance_grade: null,
    });
  wrap(
    <JudgmentCard
      document={{ ...documentFixture, relevance_grade: 1 }}
      poolId="pool-fixture"
      writable
      onDirty={() => {}}
      onSaved={() => {}}
    />,
  );
  await userEvent.click(screen.getByLabelText("Leave unjudged"));
  await userEvent.click(screen.getByRole("button", { name: "Save judgment" }));
  await waitFor(() =>
    expect(save).toHaveBeenCalledWith(
      "pool-fixture",
      "Q001",
      documentFixture.paper_id,
      null,
    ),
  );
});
it("does not claim success after failed persistence", async () => {
  vi.spyOn(evaluationApi, "judge").mockRejectedValue(
    new Error("Storage unavailable"),
  );
  const saved = vi.fn();
  wrap(
    <JudgmentCard
      document={documentFixture}
      poolId="pool-fixture"
      writable
      onDirty={() => {}}
      onSaved={saved}
    />,
  );
  await userEvent.click(screen.getByLabelText("Partially relevant (1)"));
  await userEvent.click(screen.getByRole("button", { name: "Save judgment" }));
  expect(await screen.findByRole("alert")).toHaveTextContent(
    "Storage unavailable",
  );
  expect(saved).not.toHaveBeenCalled();
  expect(screen.queryByText("Judgment saved.")).toBeNull();
});
it("ignores grade shortcuts while typing and enforces read-only state", () => {
  const { rerender } = wrap(
    <JudgmentCard
      document={documentFixture}
      poolId="pool-fixture"
      writable
      onDirty={() => {}}
      onSaved={() => {}}
    />,
  );
  const input = document.createElement("input");
  document.body.appendChild(input);
  fireEvent.keyDown(input, { key: "2" });
  expect(screen.getByLabelText("Leave unjudged")).toBeChecked();
  input.remove();
  rerender(
    <QueryClientProvider client={new QueryClient()}>
      <JudgmentCard
        document={documentFixture}
        poolId="pool-fixture"
        writable={false}
        onDirty={() => {}}
        onSaved={() => {}}
      />
    </QueryClientProvider>,
  );
  expect(screen.getByRole("button", { name: "Save judgment" })).toBeDisabled();
});
function workspaceMocks(complete = false) {
  vi.spyOn(evaluationApi, "queries").mockResolvedValue(collection);
  vi.spyOn(evaluationApi, "config").mockResolvedValue({
    enabled: true,
    mutations_enabled: true,
  });
  vi.spyOn(evaluationApi, "pools").mockResolvedValue([poolFixture]);
  vi.spyOn(evaluationApi, "progress").mockResolvedValue(progressFixture);
  vi.spyOn(evaluationApi, "runs").mockResolvedValue(
    complete ? [runFixture] : [],
  );
  vi.spyOn(evaluationApi, "benchmarks").mockResolvedValue([]);
  vi.spyOn(evaluationApi, "run").mockResolvedValue(runFixture);
  vi.spyOn(evaluationApi, "curves").mockResolvedValue({
    points: [],
    aggregate: [],
    convention: "No interpolation",
  });
}
it("shows truthful empty metrics and prevents incomplete evaluation", async () => {
  workspaceMocks();
  wrap(<EvaluationWorkspace />);
  await screen.findByText("Retrieval evaluation is not available yet.");
  await waitFor(() =>
    expect(
      screen.getByRole("button", { name: "Run evaluation" }),
    ).toBeDisabled(),
  );
  expect(await screen.findByText(/2 required judgments remain/)).toBeVisible();
});
it("renders measured fixture values and export actions", async () => {
  workspaceMocks(true);
  wrap(<EvaluationWorkspace />);
  expect(
    await screen.findByText(
      "Mean effectiveness over the same eligible queries (undefined metrics excluded)",
    ),
  ).toBeVisible();
  expect(
    within(screen.getAllByRole("table")[1]).getAllByText("0.1000"),
  ).toHaveLength(4);
  expect(screen.getByRole("link", { name: "Export report" })).toHaveAttribute(
    "href",
    expect.stringContaining("run-fixture"),
  );
});
it("rejects a malformed evaluation response at the boundary", async () => {
  vi.spyOn(globalThis, "fetch").mockResolvedValue(
    new Response(JSON.stringify({ total: "not a number" })),
  );
  await expect(evaluationApi.progress("pool-fixture")).rejects.toThrow(
    "API contract",
  );
});
