"use client";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { Search, ArrowRight } from "lucide-react";
import type { Mode } from "@/lib/api/types";
import { modes, labels, descriptions, querySchema } from "@/lib/state";
import { Button } from "../ui/button";
const schema = z.object({ q: querySchema });
export function ModeSelector({
  mode,
  onChange,
}: {
  mode: Mode;
  onChange: (m: Mode) => void;
}) {
  return (
    <div className="mode-group" role="group" aria-label="Retrieval algorithm">
      {modes.map((m) => (
        <button
          key={m}
          type="button"
          className="mode-button"
          title={descriptions[m]}
          aria-pressed={m === mode}
          onClick={() => onChange(m)}
        >
          {labels[m]}
        </button>
      ))}
    </div>
  );
}
export function SearchForm({
  initialQuery = "",
  initialMode = "hybrid",
  onSubmit,
  busy = false,
  showModes = true,
  action = "Search",
}: {
  initialQuery?: string;
  initialMode?: Mode;
  onSubmit: (q: string, mode: Mode) => void;
  busy?: boolean;
  showModes?: boolean;
  action?: string;
}) {
  const [mode, setMode] = useState(initialMode);
  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<{ q: string }>({
    resolver: zodResolver(schema),
    defaultValues: { q: initialQuery },
  });
  return (
    <form
      onSubmit={handleSubmit(({ q }) => onSubmit(q, mode))}
      aria-label={action + " research"}
    >
      <div className="search-box surface">
        <Search size={20} className="ml-3 shrink-0 text-secondary" />
        <label htmlFor="research-query" className="sr-only">
          Research query
        </label>
        <input
          id="research-query"
          {...register("q")}
          placeholder="Search research papers, topics, or scientific concepts…"
          autoComplete="off"
          aria-invalid={!!errors.q}
          aria-describedby={errors.q ? "query-error" : undefined}
        />
        <Button type="submit" disabled={busy}>
          {busy ? "Searching…" : action}
          <ArrowRight size={15} />
        </Button>
      </div>
      {errors.q && (
        <p role="alert" id="query-error" className="error-text">
          {errors.q.message}
        </p>
      )}
      {showModes && <ModeSelector mode={mode} onChange={setMode} />}
    </form>
  );
}
