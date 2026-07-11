import { supabase } from "@/lib/supabase";
import { evaluateSearchAvailability, getSearchCooldownHours } from "@/lib/rateLimit";
import { getActiveGroupId } from "@/lib/session";
import { redirect } from "next/navigation";
import FiltersEditor from "./FiltersEditor";
import PlatformStatus from "./PlatformStatus";
import RecipientsEditor from "./RecipientsEditor";
import SearchNowButton from "./SearchNowButton";
import type { FilterRow, PlatformStatusRow, RecipientRow } from "./types";

export const dynamic = "force-dynamic";

export default async function Page() {
  const groupId = await getActiveGroupId();
  if (!groupId) {
    // No debería pasar (proxy.ts ya exige una cookie válida para llegar
    // aquí), pero si pasa, mejor volver a pedir login que consultar
    // Supabase con un group_id vacío.
    redirect("/login");
  }

  const [
    { data: filters, error: filtersError },
    { data: recipients, error: recipientsError },
    { data: lastExecution, error: executionLogError },
    { data: platforms, error: platformsError },
    cooldownHours,
  ] = await Promise.all([
    supabase
      .from("filters")
      .select("id, profile_name, zona, property_type, price_max, bedrooms_min, bathrooms_min, m2_min, active")
      .eq("group_id", groupId)
      .order("created_at", { ascending: true }),
    supabase
      .from("recipients")
      .select("id, email, active")
      .eq("type", "new_listings")
      .eq("group_id", groupId)
      .order("id", { ascending: true }),
    // Caso límite conocido y aceptado: si alguien recarga la página justo
    // después de pulsar "Buscar pisos ahora", puede que el workflow real
    // todavía no haya escrito su fila en execution_log, y el botón vuelva a
    // aparecer activo durante ese minuto. No se resuelve aquí.
    supabase
      .from("execution_log")
      .select("executed_at")
      .order("executed_at", { ascending: false })
      .limit(1)
      .maybeSingle(),
    supabase
      .from("platforms")
      .select("id, name, last_checked_at, last_run_new_count")
      .order("name", { ascending: true }),
    getSearchCooldownHours(),
  ]);

  if (filtersError || recipientsError || executionLogError || platformsError) {
    return (
      <main className="page">
        <h1>cazapisos</h1>
        <p className="error">
          No se ha podido conectar con Supabase:{" "}
          {filtersError?.message ?? recipientsError?.message ?? executionLogError?.message ?? platformsError?.message}
        </p>
      </main>
    );
  }

  const { canSearch, hoursSinceLast, hoursRemaining } = evaluateSearchAvailability(
    lastExecution?.executed_at ?? null,
    cooldownHours
  );

  return (
    <main className="page">
      <h1>cazapisos</h1>
      <PlatformStatus platforms={(platforms ?? []) as PlatformStatusRow[]} />
      <SearchNowButton canSearch={canSearch} hoursSinceLast={hoursSinceLast} hoursRemaining={hoursRemaining} />
      <RecipientsEditor initialRecipients={(recipients ?? []) as RecipientRow[]} />
      <FiltersEditor initialFilters={(filters ?? []) as FilterRow[]} />
    </main>
  );
}
