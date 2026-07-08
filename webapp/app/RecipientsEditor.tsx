"use client";

import { useState, useTransition } from "react";
import { addRecipientEmail, removeRecipientEmail } from "./actions";
import type { RecipientRow } from "./types";

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

export default function RecipientsEditor({
  initialRecipients,
}: {
  initialRecipients: RecipientRow[];
}) {
  const [recipients, setRecipients] = useState(initialRecipients);
  const [newEmail, setNewEmail] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [pending, startTransition] = useTransition();

  function handleAdd() {
    const trimmed = newEmail.trim();
    if (!trimmed) return;
    if (!EMAIL_RE.test(trimmed)) {
      setError("Ese email no tiene un formato válido.");
      return;
    }
    setError(null);
    startTransition(async () => {
      const result = await addRecipientEmail(trimmed);
      if (result.error || !result.recipient) {
        setError(result.error ?? "No se ha podido guardar el email.");
        return;
      }
      setRecipients((prev) => [...prev, result.recipient!]);
      setNewEmail("");
    });
  }

  function handleRemove(id: number) {
    setError(null);
    const previous = recipients;
    setRecipients((prev) => prev.filter((r) => r.id !== id));
    startTransition(async () => {
      const result = await removeRecipientEmail(id);
      if (result.error) {
        setError(result.error);
        setRecipients(previous);
      }
    });
  }

  return (
    <section className="card">
      <h2>Emails de aviso</h2>
      <p className="card-hint">Aquí llegan los avisos de pisos nuevos que cumplen tus búsquedas.</p>
      <div className="pills">
        {recipients.map((r) => (
          <span key={r.id} className="pill">
            {r.email}
            <button
              type="button"
              className="pill-remove"
              aria-label={`Quitar ${r.email}`}
              onClick={() => handleRemove(r.id)}
              disabled={pending}
            >
              ×
            </button>
          </span>
        ))}
        {recipients.length === 0 && <p className="empty-hint">Todavía no hay ningún email añadido.</p>}
      </div>
      <div className="add-row">
        <input
          type="email"
          placeholder="nuevo.email@ejemplo.com"
          value={newEmail}
          onChange={(e) => {
            setNewEmail(e.target.value);
            if (error) setError(null);
          }}
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              e.preventDefault();
              handleAdd();
            }
          }}
          disabled={pending}
        />
        <button type="button" onClick={handleAdd} disabled={pending || !newEmail.trim()}>
          Añadir
        </button>
      </div>
      {error && <p className="error">{error}</p>}
    </section>
  );
}
