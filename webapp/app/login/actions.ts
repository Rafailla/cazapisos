"use server";

import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { supabase } from "@/lib/supabase";
import { AUTH_COOKIE_NAME, AUTH_COOKIE_MAX_AGE_SECONDS, computeSessionCookieValue } from "@/lib/authCookie";

export async function login(formData: FormData) {
  const pin = String(formData.get("pin") ?? "");
  const appPin = process.env.APP_PIN;

  const groupId = pin ? await resolveGroupId(pin, appPin) : null;

  if (!groupId) {
    redirect("/login?error=1");
  }

  const cookieStore = await cookies();
  cookieStore.set(AUTH_COOKIE_NAME, computeSessionCookieValue(groupId), {
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: "lax",
    maxAge: AUTH_COOKIE_MAX_AGE_SECONDS,
    path: "/",
  });

  redirect("/");
}

// Un PIN puede ser el de un grupo concreto (groups.pin) o, en su ausencia,
// el APP_PIN de siempre — que loguea en el grupo sin PIN propio (hoy
// 'amigos'), para no romper el acceso ya conocido por el amigo y su mujer.
async function resolveGroupId(pin: string, appPin: string | undefined): Promise<string | null> {
  const { data: matchedGroup } = await supabase.from("groups").select("id").eq("pin", pin).maybeSingle();
  if (matchedGroup) return matchedGroup.id;

  if (appPin && pin === appPin) {
    // Grupo explícito por slug, no por "el más antiguo con pin=NULL":
    // 'amigos' y 'padres' se crearon en el mismo INSERT (mismo
    // created_at), así que un order+limit(1) por created_at no está
    // garantizado por SQL y podría devolver cualquiera de los dos sin
    // avisar. 'amigos' es el grupo de fallback por diseño, así que se
    // pide por su slug directamente.
    const { data: fallbackGroup } = await supabase.from("groups").select("id").eq("slug", "amigos").maybeSingle();
    return fallbackGroup?.id ?? null;
  }

  return null;
}
