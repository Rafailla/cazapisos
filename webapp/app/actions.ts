"use server";

import { revalidatePath } from "next/cache";
import { supabase } from "@/lib/supabase";
import { triggerScrapeWorkflow } from "@/lib/github";
import { evaluateSearchAvailability } from "@/lib/rateLimit";
import type { FilterRow, RecipientRow } from "./types";

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

export type FilterPatch = {
  profile_name?: string;
  active?: boolean;
  zona?: string;
  property_type?: string | null;
  price_max?: number | null;
  bedrooms_min?: number;
  bathrooms_min?: number;
  m2_min?: number | null;
};

export type ActionResult = { error?: string };

function validatePatch(patch: FilterPatch): string | null {
  if (patch.profile_name !== undefined && patch.profile_name.trim() === "") {
    return "El nombre del perfil no puede estar vacío.";
  }
  if (patch.zona !== undefined) {
    const localidades = patch.zona
      .split(",")
      .map((z) => z.trim())
      .filter(Boolean);
    if (localidades.length === 0) {
      return "La zona no puede quedarse sin localidades.";
    }
  }
  if (patch.price_max !== undefined && patch.price_max !== null) {
    if (Number.isNaN(patch.price_max) || patch.price_max < 0) {
      return "El precio máximo debe ser un número mayor o igual que 0.";
    }
  }
  if (patch.m2_min !== undefined && patch.m2_min !== null) {
    if (Number.isNaN(patch.m2_min) || patch.m2_min < 0) {
      return "Los m2 mínimos deben ser un número mayor o igual que 0.";
    }
  }
  if (patch.bedrooms_min !== undefined && patch.bedrooms_min < 0) {
    return "Las habitaciones mínimas no pueden ser negativas.";
  }
  if (patch.bathrooms_min !== undefined && patch.bathrooms_min < 0) {
    return "Los baños mínimos no pueden ser negativos.";
  }
  return null;
}

export async function updateFilter(id: string, patch: FilterPatch): Promise<ActionResult> {
  const validationError = validatePatch(patch);
  if (validationError) return { error: validationError };

  const { error } = await supabase.from("filters").update(patch).eq("id", id);
  if (error) return { error: error.message };

  revalidatePath("/");
  return {};
}

export async function addFilter(): Promise<ActionResult & { filter?: FilterRow }> {
  const { data, error } = await supabase
    .from("filters")
    .insert({
      profile_name: "Nueva búsqueda",
      zona: "",
      property_type: null,
      price_max: null,
      bedrooms_min: 0,
      bathrooms_min: 0,
      m2_min: null,
      active: true,
    })
    .select("id, profile_name, zona, property_type, price_max, bedrooms_min, bathrooms_min, m2_min, active")
    .single();

  if (error) return { error: error.message };

  revalidatePath("/");
  return { filter: data as FilterRow };
}

export async function deleteFilter(id: string): Promise<ActionResult> {
  const { error } = await supabase.from("filters").delete().eq("id", id);
  if (error) return { error: error.message };

  revalidatePath("/");
  return {};
}

export async function addRecipientEmail(email: string): Promise<ActionResult & { recipient?: RecipientRow }> {
  const trimmed = email.trim();
  if (!EMAIL_RE.test(trimmed)) {
    return { error: "Ese email no tiene un formato válido." };
  }

  const { data, error } = await supabase
    .from("recipients")
    .insert({ email: trimmed, type: "new_listings", active: true })
    .select("id, email, active")
    .single();

  if (error) return { error: error.message };

  revalidatePath("/");
  return { recipient: data as RecipientRow };
}

export async function removeRecipientEmail(id: number): Promise<ActionResult> {
  const { error } = await supabase.from("recipients").delete().eq("id", id).eq("type", "new_listings");
  if (error) return { error: error.message };

  revalidatePath("/");
  return {};
}

export async function triggerSearch(): Promise<ActionResult> {
  // Re-comprobamos el límite de 16h en servidor: el botón solo se renderiza
  // pulsable si la página lo permite, pero una Server Action es un endpoint
  // POST alcanzable directamente, así que no basta con ocultar el botón.
  const { data } = await supabase
    .from("execution_log")
    .select("executed_at")
    .order("executed_at", { ascending: false })
    .limit(1)
    .maybeSingle();

  const { canSearch } = evaluateSearchAvailability(data?.executed_at ?? null);
  if (!canSearch) {
    return { error: "Todavía no han pasado 16 horas desde la última búsqueda." };
  }

  const result = await triggerScrapeWorkflow();
  if (result.error) return { error: result.error };

  revalidatePath("/");
  return {};
}
