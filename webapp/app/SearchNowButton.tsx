"use client";

import { useState, useTransition } from "react";
import { triggerSearch } from "./actions";

function formatHoursSince(hours: number): string {
  if (hours < 1) return "hace menos de una hora";
  const rounded = Math.floor(hours);
  return `hace ${rounded} hora${rounded === 1 ? "" : "s"}`;
}

function formatHoursRemaining(hours: number): string {
  const rounded = Math.max(1, Math.ceil(hours));
  return `dentro de ${rounded} hora${rounded === 1 ? "" : "s"}`;
}

export default function SearchNowButton({
  canSearch,
  hoursSinceLast,
  hoursRemaining,
}: {
  canSearch: boolean;
  hoursSinceLast: number | null;
  hoursRemaining: number;
}) {
  const [triggered, setTriggered] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [pending, startTransition] = useTransition();

  function handleClick() {
    setError(null);
    startTransition(async () => {
      const result = await triggerSearch();
      if (result.error) {
        setError(result.error);
        return;
      }
      setTriggered(true);
    });
  }

  if (!canSearch) {
    return (
      <section className="card search-now">
        <p className="search-now-status">
          Ya se buscó {hoursSinceLast !== null ? formatHoursSince(hoursSinceLast) : ""}. Podrás
          volver a buscar {formatHoursRemaining(hoursRemaining)}.
        </p>
      </section>
    );
  }

  if (triggered) {
    return (
      <section className="card search-now">
        <p className="search-now-confirmation">
          Búsqueda iniciada. Si hay pisos nuevos, llegará un email en unos minutos.
        </p>
      </section>
    );
  }

  return (
    <section className="card search-now">
      <button type="button" className="search-now-btn" onClick={handleClick} disabled={pending}>
        {pending ? "Iniciando búsqueda…" : "Buscar pisos ahora"}
      </button>
      {error && <p className="error">{error}</p>}
    </section>
  );
}
