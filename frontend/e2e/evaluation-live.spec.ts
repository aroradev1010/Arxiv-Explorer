import { test, expect } from "@playwright/test";
const base = "http://127.0.0.1:8001/api/v1/evaluation";
test("real HTTP backend annotation, snapshots, readiness, benchmark and export on isolated fixtures", async ({
  page,
  request,
}, info) => {
  const q = {
    id: "Q001",
    query: "quantum",
    information_need:
      "Find quantum field research in the synthetic test corpus.",
    domain: "physics",
    query_type: "exact",
    notes:
      "Browser fixture only; " +
      info.project.name +
      "; never production human ground truth",
  };
  const collection = await request.post(base + "/queries", {
    data: { queries: [q] },
  });
  expect(collection.ok()).toBe(true);
  const version = (await collection.json()).version;
  await page.goto("/evaluation");
  const poolResponse = page.waitForResponse(
    (r) =>
      r.url().endsWith("/evaluation/pools") && r.request().method() === "POST",
  );
  await page.getByRole("button", { name: "Generate pool" }).click();
  const poolId = (await (await poolResponse).json()).id;
  await expect(page.getByLabel("Candidate pool")).toHaveValue(poolId);
  await expect(
    page.getByRole("link", { name: /Open blind annotation/ }),
  ).toBeVisible();
  const incomplete = await request.post(base + "/runs", {
    data: { pool_id: poolId },
  });
  expect(incomplete.status()).toBe(409);
  await expect(
    page.getByRole("button", { name: "Run evaluation" }),
  ).toBeDisabled();
  await page.getByRole("link", { name: /Open blind annotation/ }).click();
  const docs = await (
    await request.get(
      base + `/pools/${poolId}/judgments?query_id=Q001&limit=100`,
    )
  ).json();
  await page.getByLabel("Advance to next unjudged after saving").uncheck();
  const firstId = docs.items[0].paper_id;
  await page.getByLabel("Highly relevant (2)").check();
  await page.getByRole("button", { name: "Save judgment" }).click();
  await expect(page.getByText("Judgment saved.")).toBeVisible();
  const saved = await (
    await request.get(
      base + `/pools/${poolId}/judgments?query_id=Q001&limit=100`,
    )
  ).json();
  expect(
    saved.items.find((d: { paper_id: string }) => d.paper_id === firstId)
      .relevance_grade,
  ).toBe(2);
  await page.reload();
  await page.getByLabel("Jump to paper").selectOption("0");
  await expect(page.getByLabel("Highly relevant (2)")).toBeChecked();
  // Explicit grades belong exclusively to this deterministic test database.
  for (const d of docs.items) {
    const response = await request.put(base + `/pools/${poolId}/judgments`, {
      data: { query_id: "Q001", paper_id: d.paper_id, relevance_grade: 2 },
    });
    expect(response.ok()).toBe(true);
  }
  await page.goto("/evaluation");
  await page.getByRole("button", { name: "Run evaluation" }).click();
  const table = page.getByRole("table").nth(1);
  await expect(table.locator("tbody tr")).toHaveCount(4);
  for (const row of await table.locator("tbody tr").all()) {
    await expect(row.locator("td").nth(0)).toHaveText("1.0000");
    await expect(row.locator("td").nth(2)).toHaveText("1.0000");
    await expect(row.locator("td").nth(3)).toHaveText("1.0000");
  }
  const runs = await (await request.get(base + "/runs")).json();
  const run = await (await request.get(base + "/runs/" + runs[0].id)).json();
  expect(
    run.metrics.every(
      (m: { precision: number; ndcg: number }) =>
        m.precision === 1 && m.ndcg === 1,
    ),
  ).toBe(true);
  await page.getByLabel("Warmup rounds").fill("1");
  await page.getByLabel("Measured rounds").fill("2");
  await page.getByRole("button", { name: "Start benchmark" }).click();
  await expect(page.getByText(/COMPLETED · 12\/12 executions/)).toBeVisible();
  const benchmarks = await (await request.get(base + "/benchmarks")).json();
  expect(
    Object.values(benchmarks[0].summary).every(
      (s) => (s as { count: number }).count === 2,
    ),
  ).toBe(true);
  const exported = await request.get(base + `/export?kind=run&id=${run.id}`);
  expect(exported.ok()).toBe(true);
  expect((await exported.json()).judgment_snapshot).toBeTruthy();
  expect(version).toBeTruthy();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
});
