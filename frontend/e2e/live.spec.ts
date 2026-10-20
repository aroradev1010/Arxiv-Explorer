import { test, expect } from "@playwright/test";
test("real corpus: homepage → search → filters → paper → recommendations → comparison", async ({
  page,
  request,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.goto("/");
  await expect(page.getByText("50,000", { exact: true })).toBeVisible();
  await page.screenshot({ path: "test-results/live-home.png", fullPage: true });
  await page.getByLabel("Research query").fill("graph neural networks");
  const search = page.waitForResponse(
    (r) => r.url().includes("/api/v1/search?") && r.status() === 200,
  );
  await page.getByRole("button", { name: "Search", exact: true }).click();
  const data = await (await search).json();
  await expect(
    page.getByRole("heading", {
      name: data.results[0].paper.title.replace(/\s+/g, " ").trim(),
      exact: true,
    }),
  ).toBeVisible();
  await page.screenshot({
    path: "test-results/live-search.png",
    fullPage: true,
  });
  const bm25 = page.waitForResponse(
    (r) =>
      r.url().includes("/api/v1/search?") &&
      r.url().includes("mode=bm25") &&
      r.status() === 200,
  );
  await page.getByRole("button", { name: "BM25", exact: true }).click();
  const lexical = await (await bm25).json();
  await expect(
    page
      .getByText(lexical.results[0].score.toFixed(4), { exact: true })
      .first(),
  ).toBeVisible();
  await page.getByLabel("Category", { exact: true }).selectOption("cs.LG");
  await page.getByLabel("Broad subject", { exact: true }).selectOption("cs");
  await page
    .getByLabel("Author", { exact: true })
    .fill(data.results[0].paper.authors[0]);
  await page.getByLabel("From year").fill("2015");
  await page.getByLabel("To year").fill("2025");
  const filtered = page.waitForResponse(
    (r) =>
      r.url().includes("/api/v1/search?") &&
      r.url().includes("category=cs.LG") &&
      r.status() === 200,
  );
  await page.getByRole("button", { name: "Apply filters" }).click();
  const f = await (await filtered).json();
  expect(f.results.length).toBeGreaterThan(0);
  expect(
    f.results.every((r: { paper: { categories: string[] } }) =>
      r.paper.categories.includes("cs.LG"),
    ),
  ).toBe(true);
  await page
    .getByRole("heading", {
      name: f.results[0].paper.title.replace(/\s+/g, " ").trim(),
      exact: true,
    })
    .getByRole("link")
    .click();
  await expect(
    page.getByRole("heading", {
      name: f.results[0].paper.title.replace(/\s+/g, " ").trim(),
      exact: true,
    }),
  ).toBeVisible();
  await expect(
    page.getByText("Cosine similarity", { exact: true }).first(),
  ).toBeVisible();
  await page.screenshot({
    path: "test-results/live-paper.png",
    fullPage: true,
  });
  await page.goto("/compare");
  await page.getByLabel("Research query").fill("graph neural networks");
  const compared = page.waitForResponse(
    (r) => r.url().endsWith("/api/v1/compare") && r.status() === 200,
  );
  await page.getByRole("button", { name: "Compare", exact: true }).click();
  const c = await (await compared).json();
  expect(Object.keys(c.methods)).toHaveLength(4);
  await expect(
    page.getByRole("heading", { name: "Ranking overlap" }),
  ).toBeVisible();
  await page.getByText("Explore RRF contributions").first().click();
  await expect(page.getByText(/Contributions agree/).first()).toBeVisible();
  await page.screenshot({
    path: "test-results/live-compare.png",
    fullPage: true,
  });
  const ready = await request.get("http://127.0.0.1:8000/api/v1/health/ready");
  expect(ready.ok()).toBe(true);
  expect(errors).toEqual([]);
});

test("real corpus mobile search, comparison, and screenshots", async ({
  page,
}) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/search?q=graph+neural+networks&mode=semantic");
  await expect(
    page.getByText("Cosine similarity", { exact: true }).first(),
  ).toBeVisible();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  await page.screenshot({
    path: "test-results/live-mobile-search.png",
    fullPage: false,
  });
  await page.getByRole("button", { name: "Filters", exact: true }).click();
  await expect(
    page
      .getByRole("dialog")
      .getByRole("combobox", { name: "Category", exact: true }),
  ).toBeEnabled();
  await page.getByRole("button", { name: "Close panel" }).click();
  await page.goto("/compare?q=graph+neural+networks&top_k=5");
  await expect(
    page.getByRole("heading", { name: "Ranking overlap" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Semantic", exact: true }).click();
  await expect(
    page.getByRole("region", { name: "Semantic rankings" }),
  ).toBeVisible();
  await page.screenshot({
    path: "test-results/live-mobile-compare.png",
    fullPage: false,
  });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
});
