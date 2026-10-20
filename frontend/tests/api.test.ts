import { it, expect, vi } from "vitest";
import { api, ApiError } from "@/lib/api/client";
import hybrid from "./fixtures/hybrid.json";
it("sends safely encoded requests and renders contract data without inventing fields", async () => {
  const fetcher = vi
    .spyOn(globalThis, "fetch")
    .mockResolvedValue(new Response(JSON.stringify(hybrid)));
  const result = await api.search({
    q: "graph & α",
    mode: "hybrid",
    filters: { author: "A & B", year_from: 2000 },
    offset: 10,
  });
  const url = new URL(String(fetcher.mock.calls[0][0]));
  expect(url.pathname).toBe("/api/v1/search");
  expect(url.searchParams.get("q")).toBe("graph & α");
  expect(url.searchParams.get("author")).toBe("A & B");
  expect(url.searchParams.get("offset")).toBe("10");
  expect(result.results[0].paper.id).toBe(hybrid.results[0].paper.id);
});
it("rejects malformed success payloads", async () => {
  vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response("{}"));
  await expect(api.stats()).rejects.toMatchObject({ code: "invalid_response" });
});
it("handles unreachable backend and 422", async () => {
  const mock = vi
    .spyOn(globalThis, "fetch")
    .mockRejectedValue(new TypeError("Failed to fetch"));
  await expect(api.paper("hep-th/9901001")).rejects.toMatchObject({
    code: "network_error",
  });
  mock.mockResolvedValue(
    new Response(
      JSON.stringify({
        error: {
          code: "validation_error",
          message: "Request validation failed",
        },
      }),
      { status: 422 },
    ),
  );
  await expect(api.paper("bad")).rejects.toBeInstanceOf(ApiError);
});
it("supports cancellation signals and comparison POST body", async () => {
  const c = new AbortController();
  const mock = vi
    .spyOn(globalThis, "fetch")
    .mockResolvedValue(new Response("{}"));
  await api
    .compare(
      {
        query: "quantum",
        top_k: 10,
        filters: { category: "cs.AI" },
        modes: ["bm25"],
      },
      c.signal,
    )
    .catch(() => {});
  expect(mock.mock.calls[0][1]).toMatchObject({
    method: "POST",
    body: JSON.stringify({
      query: "quantum",
      top_k: 10,
      filters: { category: "cs.AI" },
      modes: ["bm25"],
    }),
  });
});
