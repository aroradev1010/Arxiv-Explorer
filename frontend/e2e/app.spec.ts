import { test, expect, type Page } from "@playwright/test";
import hybrid from "../tests/fixtures/hybrid.json" with { type: "json" };
import bm25 from "../tests/fixtures/bm25.json" with { type: "json" };
import tfidf from "../tests/fixtures/tfidf.json" with { type: "json" };
import semantic from "../tests/fixtures/semantic.json" with { type: "json" };
import paper from "../tests/fixtures/paper.json" with { type: "json" };
import similar from "../tests/fixtures/similar.json" with { type: "json" };
import compare from "../tests/fixtures/compare.json" with { type: "json" };
import categories from "../tests/fixtures/categories.json" with { type: "json" };
import stats from "../tests/fixtures/stats.json" with { type: "json" };
async function fixtures(page: Page) {
  await page.route("**/api/v1/**", async (route) => {
    const url = new URL(route.request().url());
    const path = url.pathname.split("/api/v1/")[1];
    const data =
      path === "search"
        ? { hybrid, bm25, semantic, tfidf }[
            url.searchParams.get("mode") as "hybrid"
          ] || hybrid
        : path === "papers"
          ? paper
          : path === "papers/similar"
            ? similar
            : path === "compare"
              ? compare
              : path === "categories"
                ? categories
                : path === "system/stats"
                  ? stats
                  : {
                      status: path.endsWith("live") ? "live" : "ready",
                      reason: null,
                    };
    await route.fulfill({ json: data });
  });
}
test.beforeEach(async ({ page }) => {
  await fixtures(page);
});
test("homepage search, algorithm switching, history and details", async ({
  page,
}) => {
  await page.goto("/");
  await page.getByLabel("Research query").fill("graph neural networks");
  await page.getByRole("button", { name: "Search", exact: true }).click();
  await expect(page).toHaveURL(/\/search\?q=graph/);
  await expect(
    page.getByRole("heading", {
      name: hybrid.results[0].paper.title.replace(/\s+/g, " ").trim(),
      exact: true,
    }),
  ).toBeVisible();
  await page.getByRole("button", { name: "BM25", exact: true }).click();
  await expect(
    page.getByRole("heading", {
      name: bm25.results[0].paper.title.replace(/\s+/g, " ").trim(),
      exact: true,
    }),
  ).toBeVisible();
  await expect(page.getByText("BM25 score").first()).toBeVisible();
  await page.getByRole("button", { name: "Semantic", exact: true }).click();
  await expect(
    page.getByText("Cosine similarity", { exact: true }).first(),
  ).toBeVisible();
  await page.goBack();
  await expect(
    page.getByRole("button", { name: "BM25", exact: true }),
  ).toHaveAttribute("aria-pressed", "true");
  await page.goBack();
  await page
    .getByRole("heading", {
      name: hybrid.results[0].paper.title.replace(/\s+/g, " ").trim(),
      exact: true,
    })
    .getByRole("link")
    .click();
  await expect(page).toHaveURL(/\/papers\?arxiv_id=/);
  await expect(
    page.getByRole("heading", {
      name: paper.title.replace(/\s+/g, " ").trim(),
      exact: true,
    }),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Related in meaning" }),
  ).toBeVisible();
  await expect(
    page.getByRole("link", { name: "Open PDF ↗" }).first(),
  ).toHaveAttribute("href", "https://arxiv.org/pdf/" + paper.id);
});
test("applied filters are encoded, restored and cleared", async ({
  page,
}, testInfo) => {
  await page.goto("/search?q=graph+neural+networks&mode=hybrid&offset=20");
  if (testInfo.project.name === "mobile")
    await page.getByRole("button", { name: "Filters", exact: true }).click();
  const form = page
    .getByRole("form", { name: "Research filters" })
    .filter({ visible: true });
  await form.getByLabel("Category", { exact: true }).selectOption("cs.LG");
  await form.getByLabel("From year").fill("2015");
  await form.getByLabel("To year").fill("2025");
  const request = page.waitForRequest(
    (r) =>
      r.url().includes("/api/v1/search?") && r.url().includes("category=cs.LG"),
  );
  await form.getByRole("button", { name: "Apply filters" }).click();
  const url = new URL((await request).url());
  expect(url.searchParams.get("offset")).toBe("0");
  expect(url.searchParams.get("year_from")).toBe("2015");
  await expect(page).toHaveURL(/category=cs.LG/);
  await page.reload();
  await expect(
    page.getByRole("button", { name: "Remove category filter" }),
  ).toBeVisible();
  if (testInfo.project.name === "mobile")
    await page.getByRole("button", { name: "Filters", exact: true }).click();
  await page
    .getByRole("form", { name: "Research filters" })
    .filter({ visible: true })
    .getByRole("button", { name: "Clear filters" })
    .click();
  await expect(page).not.toHaveURL(/category=/);
});
test("comparison renders methods, actual POST filters, ranks and RRF", async ({
  page,
}, testInfo) => {
  await page.goto("/compare");
  await page.getByLabel("Research query").fill("graph neural networks");
  const request = page.waitForRequest(
    (r) => r.url().endsWith("/compare") && r.method() === "POST",
  );
  await page.getByRole("button", { name: "Compare", exact: true }).click();
  expect((await request).postDataJSON()).toMatchObject({
    query: "graph neural networks",
    top_k: 10,
    modes: ["hybrid", "tfidf", "bm25", "semantic"],
  });
  await expect(
    page.getByRole("heading", { name: "Ranking overlap" }),
  ).toBeVisible();
  if (testInfo.project.name === "mobile") {
    await page.getByRole("button", { name: "BM25", exact: true }).click();
    await expect(
      page.getByRole("region", { name: "BM25 rankings" }),
    ).toBeVisible();
    await page.getByRole("button", { name: "Hybrid", exact: true }).click();
  }
  await page.getByText("Explore RRF contributions").first().click();
  await expect(page.getByText(/Contributions agree/).first()).toBeVisible();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true);
});
test("unavailability, retry, empty, 422 and malformed responses", async ({
  page,
}) => {
  await page.route("**/api/v1/search?**", (r) =>
    r.fulfill({
      status: 503,
      json: { error: { code: "not_ready", message: "Search index not ready" } },
    }),
  );
  await page.goto("/search?q=quantum");
  await expect(page.locator("main").getByRole("alert")).toContainText(
    "Search index not ready",
  );
  await page.route("**/api/v1/search?**", (r) =>
    r.fulfill({
      json: {
        ...hybrid,
        results: [],
        pagination: { ...hybrid.pagination, returned: 0, has_more: false },
      },
    }),
  );
  await page.getByRole("button", { name: "Retry", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "No papers found" }),
  ).toBeVisible();
  await page.route("**/api/v1/search?**", (r) =>
    r.fulfill({
      status: 422,
      json: {
        error: {
          code: "invalid_pagination_window",
          message: "Window exhausted",
        },
      },
    }),
  );
  await page.getByRole("button", { name: "BM25", exact: true }).click();
  await expect(page.locator("main").getByRole("alert")).toContainText(
    "Window exhausted",
  );
});
test("theme persists, responsive shell and screenshots", async ({
  page,
}, testInfo) => {
  await page.goto("/");
  await page
    .getByRole("button", { name: "Toggle light and dark theme" })
    .click();
  const theme = await page.evaluate(() => localStorage.getItem("theme"));
  await page.reload();
  expect(await page.evaluate(() => localStorage.getItem("theme"))).toBe(theme);
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true);
  await page.screenshot({
    path: `test-results/home-${testInfo.project.name}.png`,
    fullPage: true,
  });
  await page.goto("/search?q=graph+neural+networks");
  await expect(
    page.getByRole("heading", {
      name: hybrid.results[0].paper.title.replace(/\s+/g, " ").trim(),
      exact: true,
    }),
  ).toBeVisible();
  await page.screenshot({
    path: `test-results/search-${testInfo.project.name}.png`,
    fullPage: true,
  });
  if (testInfo.project.name === "mobile") {
    await page.getByRole("button", { name: "Open navigation" }).click();
    await page
      .getByRole("dialog")
      .getByRole("link", { name: "Evaluation" })
      .click();
    await expect(page).toHaveURL(/evaluation/);
  } else {
    await page.goto("/papers?arxiv_id=" + paper.id);
    await expect(
      page.getByRole("heading", {
        name: paper.title.replace(/\s+/g, " ").trim(),
        exact: true,
      }),
    ).toBeVisible();
    await page.screenshot({
      path: "test-results/paper-desktop.png",
      fullPage: true,
    });
  }
  await page.goto("/compare?q=graph+neural+networks");
  await expect(
    page.getByRole("heading", { name: "Ranking overlap" }),
  ).toBeVisible();
  await page.screenshot({
    path: `test-results/compare-${testInfo.project.name}.png`,
    fullPage: true,
  });
});
