import { test, expect, type Page } from "@playwright/test";
import {
  collection,
  poolFixture,
  documentFixture,
  secondDocument,
  progressFixture,
  runFixture,
  benchmarkFixture,
} from "../tests/evaluation-fixtures";

async function fixtureRoutes(page: Page) {
  const grades: Record<string, number | null> = {};
  let pool = false;
  let run = false;
  let benchmark = false;
  await page.route("**/api/v1/**", async (route) => {
    const url = new URL(route.request().url());
    const path = url.pathname.split("/api/v1/")[1];
    const method = route.request().method();
    const docs = [documentFixture, secondDocument].map((d) => ({
      ...d,
      relevance_grade: grades[d.paper_id] ?? null,
    }));
    const judged = docs.filter((d) => d.relevance_grade !== null).length;
    const progress = {
      ...progressFixture,
      judged,
      unjudged: 2 - judged,
      missing_required: 2 - judged,
      eligible_queries: judged === 2 ? 1 : 0,
      queries: [
        {
          ...progressFixture.queries[0],
          judged,
          unjudged: 2 - judged,
          missing_required: 2 - judged,
          percent: judged * 50,
          status: judged === 2 ? "READY" : "INCOMPLETE",
          grades: {
            "0": docs.filter((d) => d.relevance_grade === 0).length,
            "1": 0,
            "2": docs.filter((d) => d.relevance_grade === 2).length,
          },
        },
      ],
    };
    let data: unknown = { status: "ready", reason: null };
    if (path === "evaluation/config")
      data = { enabled: true, mutations_enabled: true };
    else if (path === "evaluation/queries") data = collection;
    else if (path === "evaluation/pools") {
      if (method === "POST") {
        pool = true;
        data = poolFixture;
      } else data = pool ? [poolFixture] : [];
    } else if (path === "evaluation/progress") data = progress;
    else if (path.endsWith("/judgments")) {
      if (method === "PUT") {
        const body = route.request().postDataJSON();
        grades[body.paper_id] = body.relevance_grade;
        data = { saved: true, ...body };
      } else data = { total: 2, offset: 0, items: docs };
    } else if (path === "evaluation/runs") {
      if (method === "POST") {
        run = true;
        data = runFixture;
      } else data = run ? [runFixture] : [];
    } else if (path.endsWith("/curves"))
      data = {
        points: [],
        aggregate: runFixture.metrics.flatMap((m) =>
          m.curves.map((p) => ({
            ...p,
            algorithm: m.algorithm,
            query_count: 1,
          })),
        ),
        convention: "Macro mean by rank; no interpolation",
      };
    else if (path === "evaluation/runs/run-fixture") data = runFixture;
    else if (path === "evaluation/benchmarks") {
      if (method === "POST") {
        benchmark = true;
        data = benchmarkFixture;
      } else data = benchmark ? [benchmarkFixture] : [];
    } else if (path === "evaluation/export") {
      await route.fulfill({
        body: "fixture export",
        headers: {
          "Content-Disposition": 'attachment; filename="fixture.csv"',
        },
      });
      return;
    }
    await route.fulfill({ json: data });
  });
}
test("annotation persists, incomplete metrics stay absent, completed fixtures and benchmarks render", async ({
  page,
}, info) => {
  await fixtureRoutes(page);
  await page.goto("/evaluation");
  await expect(
    page.getByText("Retrieval evaluation is not available yet."),
  ).toBeVisible();
  await page.getByRole("button", { name: "Generate pool" }).click();
  await expect(
    page.getByRole("link", { name: /Open blind annotation/ }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Run evaluation" }),
  ).toBeDisabled();
  await page.getByRole("link", { name: /Open blind annotation/ }).click();
  await expect(
    page.getByRole("heading", { name: "Synthetic evaluation paper A" }),
  ).toBeVisible();
  await page.getByLabel("Highly relevant (2)").check();
  await page.getByRole("button", { name: "Save judgment" }).click();
  await expect(
    page.getByRole("heading", { name: "Synthetic evaluation paper B" }),
  ).toBeVisible();
  await page.reload();
  await expect(page.getByText(/1\/2 judged/)).toBeVisible();
  await page
    .getByRole("button", { name: "Previous paper", exact: true })
    .click();
  await expect(page.getByLabel("Highly relevant (2)")).toBeChecked();
  await page.getByRole("button", { name: "Next paper", exact: true }).click();
  await page.getByLabel("Not relevant (0)", { exact: true }).check();
  await page.getByRole("button", { name: "Save judgment" }).click();
  await expect(page.getByText(/2\/2 judged/)).toBeVisible();
  await page.screenshot({
    path: `test-results/evaluation-judge-${info.project.name}.png`,
    fullPage: true,
  });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  await page.getByRole("link", { name: "Return to query list" }).click();
  await page.getByRole("button", { name: "Run evaluation" }).click();
  await expect(
    page.getByRole("table").nth(1).getByText("0.1000", { exact: true }),
  ).toHaveCount(4);
  await expect(
    page.getByRole("img", {
      name: "Uninterpolated precision versus pooled recall by algorithm",
    }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Start benchmark" }).click();
  await expect(page.getByText(/4\/4 executions/)).toBeVisible();
  await expect(
    page.getByRole("columnheader", { name: "P95 ms" }),
  ).toBeVisible();
  await expect(page.getByRole("link", { name: "Export report" })).toBeVisible();
  await page.screenshot({
    path: `test-results/evaluation-dashboard-${info.project.name}.png`,
    fullPage: true,
  });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
});
test("unsaved annotations require discard confirmation and failures do not navigate", async ({
  page,
}) => {
  await fixtureRoutes(page);
  await page.goto("/evaluation");
  await page.getByRole("button", { name: "Generate pool" }).click();
  await page.getByRole("link", { name: /Open blind annotation/ }).click();
  await page.getByLabel("Partially relevant (1)").check();
  const declinedBack = new Promise<void>((resolve) =>
    page.once("dialog", async (d) => {
      await d.dismiss();
      resolve();
    }),
  );
  await page.evaluate(() => window.history.back());
  await declinedBack;
  await expect(page).toHaveURL(/evaluation\/judge/);
  page.once("dialog", (d) => d.dismiss());
  await page.getByRole("button", { name: "Next paper", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Synthetic evaluation paper A" }),
  ).toBeVisible();
  await page.route("**/evaluation/pools/*/judgments", async (route) => {
    if (route.request().method() === "PUT")
      await route.fulfill({
        status: 503,
        json: {
          error: {
            code: "storage_error",
            message: "Unable to save fixture judgment",
          },
        },
      });
    else await route.fallback();
  });
  await page.getByRole("button", { name: "Save judgment" }).click();
  await expect(
    page
      .getByRole("alert")
      .filter({ hasText: "Unable to save fixture judgment" }),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Synthetic evaluation paper A" }),
  ).toBeVisible();
});
