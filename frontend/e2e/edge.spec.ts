import { test, expect } from "@playwright/test";
import hybrid from "../tests/fixtures/hybrid.json" with { type: "json" };
import categories from "../tests/fixtures/categories.json" with { type: "json" };
import paper from "../tests/fixtures/paper.json" with { type: "json" };
import compare from "../tests/fixtures/compare.json" with { type: "json" };
test.beforeEach(async ({ page }) => {
  await page.route("**/api/v1/categories", (r) =>
    r.fulfill({ json: categories }),
  );
});
test("network failure and malformed success both provide retry", async ({
  page,
}) => {
  await page.route("**/api/v1/search?**", (r) => r.abort());
  await page.goto("/search?q=quantum");
  await expect(page.locator("main").getByRole("alert")).toContainText(
    "Search service unavailable",
  );
  await page.route("**/api/v1/search?**", (r) =>
    r.fulfill({ json: { results: "broken" } }),
  );
  await page.getByRole("button", { name: "Retry", exact: true }).click();
  await expect(page.locator("main").getByRole("alert")).toContainText(
    "does not match the API contract",
  );
});
test("legacy paper ID is encoded and recommendation failure leaves metadata readable", async ({
  page,
}) => {
  await page.route("**/api/v1/papers?**", (r) =>
    r.fulfill({
      json: {
        ...paper,
        id: "hep-th/9901001",
        authors: [],
        authors_text: "Synthetic Test Collaboration",
        authors_source: "raw_only",
      },
    }),
  );
  await page.route("**/api/v1/papers/similar?**", (r) =>
    r.fulfill({
      status: 503,
      json: {
        error: { code: "not_ready", message: "Recommendations unavailable" },
      },
    }),
  );
  const request = page.waitForRequest((r) =>
    r.url().includes("/api/v1/papers?"),
  );
  await page.goto("/papers?arxiv_id=hep-th%2F9901001");
  expect(new URL((await request).url()).searchParams.get("arxiv_id")).toBe(
    "hep-th/9901001",
  );
  await expect(page.getByText("Synthetic Test Collaboration")).toBeVisible();
  await expect(page.getByRole("link", { name: "Open PDF ↗" })).toHaveAttribute(
    "href",
    "https://arxiv.org/pdf/hep-th/9901001",
  );
  await expect(page.locator("main").getByRole("alert")).toContainText(
    "Recommendations unavailable",
  );
  await page.route("**/api/v1/papers?**", (r) =>
    r.fulfill({
      status: 404,
      json: {
        error: {
          code: "paper_not_found",
          message: "Paper not present in the indexed corpus",
        },
      },
    }),
  );
  await page.goto("/papers?arxiv_id=9912.12345");
  await expect(
    page.getByRole("heading", { name: "Paper not found" }),
  ).toBeVisible();
});
test("pagination respects the returned window and mode changes reset offset", async ({
  page,
}) => {
  await page.route("**/api/v1/search?**", (r) => {
    const url = new URL(r.request().url());
    const offset = Number(url.searchParams.get("offset"));
    return r.fulfill({
      json: {
        ...hybrid,
        mode: url.searchParams.get("mode") || "hybrid",
        results: hybrid.results.map((v, i) => ({ ...v, rank: offset + i + 1 })),
        pagination: {
          ...hybrid.pagination,
          offset,
          limit: 10,
          ranking_window_size: 20,
          has_more: offset < 10,
        },
      },
    });
  });
  await page.goto("/search?q=quantum&mode=hybrid");
  await expect(
    page.getByRole("button", { name: "Next", exact: true }),
  ).toBeEnabled();
  await page.getByRole("button", { name: "Next", exact: true }).click();
  await expect(page).toHaveURL(/offset=10/);
  await expect(
    page.getByRole("button", { name: "Next", exact: true }),
  ).toBeDisabled();
  await page.getByRole("button", { name: "BM25", exact: true }).click();
  await expect(page).toHaveURL(/offset=0/);
});
test("slow old mode cannot replace newer mode results", async ({ page }) => {
  await page.route("**/api/v1/search?**", async (r) => {
    const mode = new URL(r.request().url()).searchParams.get("mode");
    if (mode === "bm25")
      await new Promise((resolve) => setTimeout(resolve, 600));
    await r
      .fulfill({
        json: {
          ...hybrid,
          mode,
          results: hybrid.results.map((v) => ({ ...v, algorithm: mode })),
        },
      })
      .catch(() => {});
  });
  await page.goto("/search?q=quantum&mode=hybrid");
  await expect(
    page.getByText("RRF score", { exact: true }).first(),
  ).toBeVisible();
  await page.getByRole("button", { name: "BM25", exact: true }).click();
  await page.getByRole("button", { name: "Semantic", exact: true }).click();
  await expect(
    page.getByText("Cosine similarity", { exact: true }).first(),
  ).toBeVisible();
  await expect(page.getByText("BM25 score", { exact: true })).toHaveCount(0);
});
test("comparison top-K, repetition, filters and Back restore real request state", async ({
  page,
}) => {
  await page.route("**/api/v1/compare", (r) => r.fulfill({ json: compare }));
  await page.goto("/compare?q=quantum&top_k=10");
  await expect(
    page.getByRole("heading", { name: "Ranking overlap" }),
  ).toBeVisible();
  const changed = page.waitForRequest((r) =>
    r.url().endsWith("/api/v1/compare"),
  );
  await page
    .getByRole("combobox", { name: "Results per method" })
    .selectOption("5");
  expect((await changed).postDataJSON().top_k).toBe(5);
  await page.goBack();
  await expect(
    page.getByRole("combobox", { name: "Results per method" }),
  ).toHaveValue("10");
  const repeat = page.waitForRequest((r) =>
    r.url().endsWith("/api/v1/compare"),
  );
  await page.getByRole("button", { name: "Compare", exact: true }).click();
  expect((await repeat).postDataJSON().query).toBe("quantum");
  await page.getByText("Apply the same filters to every method").click();
  await page
    .getByRole("combobox", { name: "Category", exact: true })
    .selectOption("cs.LG");
  const filtered = page.waitForRequest((r) =>
    r.url().endsWith("/api/v1/compare"),
  );
  await page.getByRole("button", { name: "Apply filters" }).click();
  expect((await filtered).postDataJSON().filters.category).toBe("cs.LG");
});
test("tablet and mobile page widths stay contained", async ({ page }) => {
  await page.route("**/api/v1/search?**", (r) => r.fulfill({ json: hybrid }));
  await page.route("**/api/v1/compare", (r) => r.fulfill({ json: compare }));
  for (const width of [360, 768, 1024]) {
    await page.setViewportSize({ width, height: 900 });
    for (const url of ["/search?q=quantum", "/compare?q=quantum"]) {
      await page.goto(url);
      await expect(
        page.getByRole("heading", {
          name: url.startsWith("/search")
            ? "Find your next connection."
            : "Ranking overlap",
        }),
      ).toBeVisible();
      expect(
        await page.evaluate(
          () => document.documentElement.scrollWidth <= window.innerWidth,
        ),
      ).toBe(true);
    }
  }
});
