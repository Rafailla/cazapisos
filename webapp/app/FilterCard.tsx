"use client";

import { useState, useTransition } from "react";
import { deleteFilter, updateFilter, type FilterPatch } from "./actions";
import type { FilterRow } from "./types";

const PROPERTY_TYPES: { value: string; label: string }[] = [
  { value: "", label: "Cualquiera" },
  { value: "piso", label: "Piso" },
  { value: "casa", label: "Casa" },
  { value: "chalet", label: "Chalet" },
  { value: "atico", label: "Ático" },
  { value: "duplex", label: "Dúplex" },
];

// Mismo vocabulario normalizado que produce el scraper en las 4
// plataformas (ver scraper/platforms/*.py y CLAUDE.md, sección "Filtros
// nuevos: ascensor y planta") — "" = indiferente (floor_preference=null).
const FLOOR_OPTIONS: { value: string; label: string }[] = [
  { value: "", label: "Indiferente" },
  { value: "bajo", label: "Bajo" },
  { value: "entresuelo", label: "Entresuelo" },
  { value: "1", label: "1ª planta" },
  { value: "2", label: "2ª planta" },
  { value: "3", label: "3ª planta" },
  { value: "4", label: "4ª planta" },
  { value: "5", label: "5ª planta" },
  { value: "6", label: "6ª planta" },
  { value: "7", label: "7ª planta" },
  { value: "8", label: "8ª planta" },
  { value: "9", label: "9ª planta" },
  { value: "10", label: "10ª planta" },
  { value: "atico", label: "Ático" },
];

function zonaToList(zona: string | null): string[] {
  return (zona ?? "")
    .split(",")
    .map((z) => z.trim())
    .filter(Boolean);
}

export default function FilterCard({
  filter,
  onUpdated,
  onDeleted,
}: {
  filter: FilterRow;
  onUpdated: (id: string, patch: FilterPatch) => void;
  onDeleted: (id: string) => void;
}) {
  const [pending, startTransition] = useTransition();
  const [error, setError] = useState<string | null>(null);
  const [confirmingDelete, setConfirmingDelete] = useState(false);
  const [nameDraft, setNameDraft] = useState(filter.profile_name);
  const [priceDraft, setPriceDraft] = useState(filter.price_max?.toString() ?? "");
  const [m2Draft, setM2Draft] = useState(filter.m2_min?.toString() ?? "");
  const [newLocalidad, setNewLocalidad] = useState("");

  const localidades = zonaToList(filter.zona);

  function save(patch: FilterPatch, onError?: () => void) {
    setError(null);
    startTransition(async () => {
      const result = await updateFilter(filter.id, patch);
      if (result.error) {
        setError(result.error);
        onError?.();
        return;
      }
      onUpdated(filter.id, patch);
    });
  }

  function handleNameBlur() {
    const trimmed = nameDraft.trim();
    if (!trimmed) {
      setError("El nombre no puede estar vacío.");
      setNameDraft(filter.profile_name);
      return;
    }
    if (trimmed === filter.profile_name) return;
    save({ profile_name: trimmed }, () => setNameDraft(filter.profile_name));
  }

  function handlePriceBlur() {
    const trimmed = priceDraft.trim();
    if (trimmed === "") {
      if (filter.price_max === null) return;
      save({ price_max: null });
      return;
    }
    const value = Number(trimmed);
    if (Number.isNaN(value) || value < 0) {
      setError("El precio máximo debe ser un número mayor o igual que 0.");
      setPriceDraft(filter.price_max?.toString() ?? "");
      return;
    }
    save({ price_max: value }, () => setPriceDraft(filter.price_max?.toString() ?? ""));
  }

  function handleM2Blur() {
    const trimmed = m2Draft.trim();
    if (trimmed === "") {
      if (filter.m2_min === null) return;
      save({ m2_min: null });
      return;
    }
    const value = Number(trimmed);
    if (Number.isNaN(value) || value < 0) {
      setError("Los m2 mínimos deben ser un número mayor o igual que 0.");
      setM2Draft(filter.m2_min?.toString() ?? "");
      return;
    }
    save({ m2_min: value }, () => setM2Draft(filter.m2_min?.toString() ?? ""));
  }

  function stepBedrooms(delta: number) {
    const next = Math.max(0, (filter.bedrooms_min ?? 0) + delta);
    save({ bedrooms_min: next });
  }

  function stepBathrooms(delta: number) {
    const next = Math.max(0, (filter.bathrooms_min ?? 0) + delta);
    save({ bathrooms_min: next });
  }

  function removeLocalidad(loc: string) {
    const next = localidades.filter((l) => l !== loc);
    if (next.length === 0) {
      setError("La zona no puede quedarse sin localidades.");
      return;
    }
    save({ zona: next.join(", ") });
  }

  function addLocalidad() {
    const trimmed = newLocalidad.trim();
    if (!trimmed) return;
    if (localidades.some((l) => l.toLowerCase() === trimmed.toLowerCase())) {
      setNewLocalidad("");
      return;
    }
    save({ zona: [...localidades, trimmed].join(", ") });
    setNewLocalidad("");
  }

  function handleDelete() {
    setError(null);
    startTransition(async () => {
      const result = await deleteFilter(filter.id);
      if (result.error) {
        setError(result.error);
        setConfirmingDelete(false);
        return;
      }
      onDeleted(filter.id);
    });
  }

  return (
    <article className={`filter-card${filter.active ? "" : " inactive"}`}>
      <header className="filter-card-header">
        <input
          className="profile-name"
          value={nameDraft}
          onChange={(e) => setNameDraft(e.target.value)}
          onBlur={handleNameBlur}
          disabled={pending}
        />
        <label className="switch">
          <input
            type="checkbox"
            checked={filter.active}
            onChange={(e) => save({ active: e.target.checked })}
            disabled={pending}
          />
          <span className="switch-track" />
          <span className="switch-label">{filter.active ? "Activo" : "Inactivo"}</span>
        </label>
      </header>

      <div className="field">
        <span className="field-label">Zona</span>
        <div className="pills">
          {localidades.map((loc) => (
            <span key={loc} className="pill">
              {loc}
              <button
                type="button"
                className="pill-remove"
                onClick={() => removeLocalidad(loc)}
                disabled={pending}
                aria-label={`Quitar ${loc}`}
              >
                ×
              </button>
            </span>
          ))}
        </div>
        <div className="add-row">
          <input
            placeholder="Añadir localidad"
            value={newLocalidad}
            onChange={(e) => setNewLocalidad(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                e.preventDefault();
                addLocalidad();
              }
            }}
            disabled={pending}
          />
          <button type="button" onClick={addLocalidad} disabled={pending || !newLocalidad.trim()}>
            Añadir
          </button>
        </div>
      </div>

      <div className="field-row">
        <div className="field">
          <span className="field-label">Tipo de vivienda</span>
          <select
            value={filter.property_type ?? ""}
            onChange={(e) => save({ property_type: e.target.value === "" ? null : e.target.value })}
            disabled={pending}
          >
            {PROPERTY_TYPES.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
        </div>

        <div className="field">
          <span className="field-label">Precio máximo (€)</span>
          <input
            type="number"
            min={0}
            placeholder="Sin límite"
            value={priceDraft}
            onChange={(e) => setPriceDraft(e.target.value)}
            onBlur={handlePriceBlur}
            disabled={pending}
          />
        </div>

        <div className="field">
          <span className="field-label">m2 mínimos</span>
          <input
            type="number"
            min={0}
            placeholder="Sin límite"
            value={m2Draft}
            onChange={(e) => setM2Draft(e.target.value)}
            onBlur={handleM2Blur}
            disabled={pending}
          />
        </div>
      </div>

      <div className="field-row">
        <div className="field">
          <span className="field-label">Habitaciones mínimas</span>
          <div className="stepper">
            <button
              type="button"
              onClick={() => stepBedrooms(-1)}
              disabled={pending || (filter.bedrooms_min ?? 0) <= 0}
            >
              −
            </button>
            <span>{filter.bedrooms_min ?? 0}</span>
            <button type="button" onClick={() => stepBedrooms(1)} disabled={pending}>
              +
            </button>
          </div>
        </div>

        <div className="field">
          <span className="field-label">Baños mínimos</span>
          <div className="stepper">
            <button
              type="button"
              onClick={() => stepBathrooms(-1)}
              disabled={pending || (filter.bathrooms_min ?? 0) <= 0}
            >
              −
            </button>
            <span>{filter.bathrooms_min ?? 0}</span>
            <button type="button" onClick={() => stepBathrooms(1)} disabled={pending}>
              +
            </button>
          </div>
        </div>
      </div>

      <div className="field-row">
        <div className="field">
          <span className="field-label">Planta</span>
          <select
            value={filter.floor_preference ?? ""}
            onChange={(e) => save({ floor_preference: e.target.value === "" ? null : e.target.value })}
            disabled={pending}
          >
            {FLOOR_OPTIONS.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
        </div>

        <div className="field">
          <span className="field-label">Ascensor</span>
          <label className="switch">
            <input
              type="checkbox"
              checked={filter.requires_elevator}
              onChange={(e) => save({ requires_elevator: e.target.checked })}
              disabled={pending}
            />
            <span className="switch-track" />
            <span className="switch-label">{filter.requires_elevator ? "Requerido" : "Indiferente"}</span>
          </label>
        </div>
      </div>

      {error && <p className="error">{error}</p>}

      <footer className="filter-card-footer">
        {confirmingDelete ? (
          <div className="confirm-delete">
            <span>¿Seguro que quieres eliminar esta búsqueda?</span>
            <button type="button" className="danger" onClick={handleDelete} disabled={pending}>
              Sí, eliminar
            </button>
            <button type="button" onClick={() => setConfirmingDelete(false)} disabled={pending}>
              Cancelar
            </button>
          </div>
        ) : (
          <button type="button" className="danger-link" onClick={() => setConfirmingDelete(true)}>
            Eliminar búsqueda
          </button>
        )}
      </footer>
    </article>
  );
}
