import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";
import { AUTH_COOKIE_NAME, verifySessionCookieValue } from "@/lib/authCookie";

// Nota: en Next.js 16 el fichero "middleware.ts" está deprecado en favor de
// "proxy.ts" (mismo mecanismo, nuevo nombre) — ver node_modules/next/dist/docs/
// 01-app/03-api-reference/03-file-conventions/proxy.md. Se usa proxy.ts aquí
// a propósito en vez del middleware.ts pedido originalmente.

export function proxy(request: NextRequest) {
  const cookie = request.cookies.get(AUTH_COOKIE_NAME);

  // Solo hace falta verificar la firma (sin llamar a Supabase en cada
  // petición): qué grupo es exactamente ya no importa aquí, cualquier
  // cookie válida basta para pasar la puerta. Cada Server Action/página
  // vuelve a resolver el group_id activo por su cuenta (ver lib/session.ts)
  // para saber A QUÉ datos concretos dar acceso.
  if (verifySessionCookieValue(cookie?.value)) {
    return NextResponse.next();
  }

  return NextResponse.redirect(new URL("/login", request.url));
}

export const config = {
  matcher: ["/((?!login|_next/static|_next/image|favicon.ico).*)"],
};
