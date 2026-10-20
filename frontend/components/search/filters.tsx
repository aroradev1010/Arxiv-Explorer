"use client";
import { useState, type FormEvent } from "react";
import type { Filters } from "@/lib/api/types";
import { filterSchema } from "@/lib/state";
import { useCategories } from "@/hooks/queries";
import { Button } from "../ui/button";
import { ErrorState } from "../ui/states";
export function FilterForm({
  filters,
  onApply,
  onClear,
  id = "filters",
}: {
  filters: Filters;
  onApply: (v: Filters) => void;
  onClear: () => void;
  id?: string;
}) {
  const categories = useCategories();
  const [error, setError] = useState("");
  function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const data = new FormData(e.currentTarget);
    const raw: Record<string, string> = {};
    for (const [k, v] of data) if (String(v).trim()) raw[k] = String(v).trim();
    const parsed = filterSchema.safeParse(raw);
    if (!parsed.success) {
      setError(parsed.error.issues.map((i) => i.message).join(" "));
      return;
    }
    setError("");
    onApply(parsed.data);
  }
  return (
    <form onSubmit={submit} aria-label="Research filters">
      <h2 className="mb-6 text-base">Refine your research</h2>
      {categories.isError && (
        <ErrorState
          error={categories.error}
          retry={() => categories.refetch()}
        />
      )}
      <div className="field">
        <label htmlFor={id + "-category"}>Category</label>
        <select
          id={id + "-category"}
          name="category"
          defaultValue={filters.category || ""}
          disabled={categories.isPending}
        >
          <option value="">All categories</option>
          {filters.category &&
            !categories.data?.categories.some(
              (c) => c.code === filters.category,
            ) && <option>{filters.category}</option>}
          {categories.data?.categories.map((c) => (
            <option key={c.code} value={c.code}>
              {c.name || c.code} ({c.count.toLocaleString()})
            </option>
          ))}
        </select>
      </div>
      <div className="field">
        <label htmlFor={id + "-subject"}>Broad subject</label>
        <select
          id={id + "-subject"}
          name="subject"
          defaultValue={filters.subject || ""}
          disabled={categories.isPending}
        >
          <option value="">All subjects</option>
          {filters.subject &&
            !categories.data?.subjects.some(
              (c) => c.code === filters.subject,
            ) && <option>{filters.subject}</option>}
          {categories.data?.subjects.map((c) => (
            <option key={c.code} value={c.code}>
              {c.name || c.code} ({c.count.toLocaleString()})
            </option>
          ))}
        </select>
      </div>
      <div className="field-row">
        <label className="field" htmlFor={id + "-from"}>
          From year
          <input
            id={id + "-from"}
            type="number"
            name="year_from"
            min={1991}
            max={2100}
            placeholder="1991"
            defaultValue={filters.year_from ?? ""}
          />
        </label>
        <label className="field" htmlFor={id + "-to"}>
          To year
          <input
            id={id + "-to"}
            type="number"
            name="year_to"
            min={1991}
            max={2100}
            placeholder="2100"
            defaultValue={filters.year_to ?? ""}
          />
        </label>
      </div>
      <div className="field">
        <label htmlFor={id + "-author"}>Author</label>
        <input
          id={id + "-author"}
          name="author"
          maxLength={200}
          defaultValue={filters.author || ""}
          placeholder="Name contains…"
        />
        <small>Name text matching; identities are not verified.</small>
      </div>
      {error && (
        <p role="alert" className="error-text">
          {error}
        </p>
      )}
      <Button type="submit" className="w-full">
        Apply filters
      </Button>
      <Button
        type="button"
        variant="ghost"
        className="mt-2 w-full"
        onClick={onClear}
      >
        Clear filters
      </Button>
    </form>
  );
}
