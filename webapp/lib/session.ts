import "server-only";
import { cookies } from "next/headers";
import { AUTH_COOKIE_NAME, verifySessionCookieValue } from "./authCookie";

// group_id activo de la sesión actual (o null si la cookie falta/no es
// válida — no debería pasar en páginas protegidas por proxy.ts, pero cada
// consumidor decide qué hacer si ocurre en vez de asumir que siempre hay
// sesión).
export async function getActiveGroupId(): Promise<string | null> {
  const cookieStore = await cookies();
  return verifySessionCookieValue(cookieStore.get(AUTH_COOKIE_NAME)?.value);
}
