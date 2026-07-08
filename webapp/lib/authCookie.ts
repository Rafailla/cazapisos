import crypto from "crypto";

// No "server-only": este módulo importa el módulo nativo "crypto", que ya no
// existe en el navegador, así que solo puede usarse desde código de servidor
// (proxy.ts y app/login/actions.ts).

export const AUTH_COOKIE_NAME = "cazapisos_auth";
export const AUTH_COOKIE_MAX_AGE_SECONDS = 60 * 60 * 24 * 180; // 180 días

// Nunca guardamos el PIN en texto plano en la cookie: guardamos un hash. Así,
// aunque alguien inspeccione las cookies del navegador, no ve el PIN.
export function computeAuthCookieValue(pin: string): string {
  return crypto.createHash("sha256").update(pin).digest("hex");
}
