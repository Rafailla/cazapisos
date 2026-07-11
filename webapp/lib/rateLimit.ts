import "server-only";
import { supabase } from "./supabase";

// Valor de reserva si app_settings no tiene la fila (o trae algo que no es
// un número válido) — no debe romper el botón "Buscar ahora" por eso.
export const DEFAULT_SEARCH_COOLDOWN_HOURS = 16;

const COOLDOWN_SETTING_KEY = "manual_trigger_cooldown_hours";

export type SearchAvailability = {
  canSearch: boolean;
  hoursSinceLast: number | null;
  hoursRemaining: number;
};

// Lee el límite de horas desde app_settings en vez de una constante fija,
// para que el dueño pueda cambiarlo (o ponerlo a 0 para quitar el límite)
// directamente en Supabase, sin tocar código ni redeploy.
export async function getSearchCooldownHours(): Promise<number> {
  const { data } = await supabase.from("app_settings").select("value").eq("key", COOLDOWN_SETTING_KEY).maybeSingle();

  const parsed = data?.value !== undefined ? Number(data.value) : NaN;
  return Number.isFinite(parsed) && parsed >= 0 ? parsed : DEFAULT_SEARCH_COOLDOWN_HOURS;
}

export function evaluateSearchAvailability(lastExecutedAt: string | null, cooldownHours: number): SearchAvailability {
  if (!lastExecutedAt) {
    return { canSearch: true, hoursSinceLast: null, hoursRemaining: 0 };
  }

  const hoursSinceLast = (Date.now() - new Date(lastExecutedAt).getTime()) / (1000 * 60 * 60);
  const hoursRemaining = Math.max(0, cooldownHours - hoursSinceLast);

  return {
    canSearch: hoursSinceLast >= cooldownHours,
    hoursSinceLast,
    hoursRemaining,
  };
}
