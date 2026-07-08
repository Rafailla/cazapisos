import { supabase } from "@/lib/supabase";
import { evaluateSearchAvailability } from "@/lib/rateLimit";
import FiltersEditor from "./FiltersEditor";
import RecipientsEditor from "./RecipientsEditor";
import SearchNowButton from "./SearchNowButton";
import type { FilterRow, RecipientRow } from "./types";

export const dynamic = "force-dynamic";

export default async function Page() {
  const [
    { data: filters, error: filtersError },
    { data: recipients, error: recipientsError },
    { data: lastExecution, error: executionLogError },
  ] = await Promise.all([
    supabase
      .from("filters")
      .select("id, profile_name, zona, property_type, price_max, bedrooms_min, bathrooms_min, m2_min, active")
      .order("created_at", { ascending: true }),
    supabase
      .from("recipients")
      .select("id, email, active")
      .eq("type", "new_listings")
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
  ]);

  if (filtersError || recipientsError || executionLogError) {
    return (
      <main className="page">
        <h1>cazapisos</h1>
        <p className="error">
          No se ha podido conectar con Supabase:{" "}
          {filtersError?.message ?? recipientsError?.message ?? executionLogError?.message}
        </p>
      </main>
    );
  }

  const { canSearch, hoursSinceLast, hoursRemaining } = evaluateSearchAvailability(
    lastExecution?.executed_at ?? null
  );

  return (
    <main className="page">
      <h1>cazapisos</h1>
      <SearchNowButton canSearch={canSearch} hoursSinceLast={hoursSinceLast} hoursRemaining={hoursRemaining} />
      <RecipientsEditor initialRecipients={(recipients ?? []) as RecipientRow[]} />
      <FiltersEditor initialFilters={(filters ?? []) as FilterRow[]} />
    </main>
  );
}
