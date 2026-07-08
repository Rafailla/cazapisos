"use client";

import { useState, useTransition } from "react";
import { addFilter, type FilterPatch } from "./actions";
import FilterCard from "./FilterCard";
import type { FilterRow } from "./types";

export default function FiltersEditor({ initialFilters }: { initialFilters: FilterRow[] }) {
  const [filters, setFilters] = useState(initialFilters);
  const [error, setError] = useState<string | null>(null);
  const [pending, startTransition] = useTransition();

  function handleAdd() {
    setError(null);
    startTransition(async () => {
      const result = await addFilter();
      if (result.error || !result.filter) {
        setError(result.error ?? "No se ha podido crear la búsqueda.");
        return;
      }
      setFilters((prev) => [...prev, result.filter!]);
    });
  }

  function handleUpdated(id: string, patch: FilterPatch) {
    setFilters((prev) => prev.map((f) => (f.id === id ? { ...f, ...patch } : f)));
  }

  function handleDeleted(id: string) {
    setFilters((prev) => prev.filter((f) => f.id !== id));
  }

  return (
    <section className="filters-section">
      <h2>Perfiles de búsqueda</h2>
      {filters.length === 0 && <p className="empty-hint">Todavía no hay ningún perfil de búsqueda.</p>}
      <div className="filter-grid">
        {filters.map((f) => (
          <FilterCard key={f.id} filter={f} onUpdated={handleUpdated} onDeleted={handleDeleted} />
        ))}
      </div>
      <button type="button" className="add-filter-btn" onClick={handleAdd} disabled={pending}>
        + Añadir nueva búsqueda
      </button>
      {error && <p className="error">{error}</p>}
    </section>
  );
}
