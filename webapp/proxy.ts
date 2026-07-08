import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";
import { AUTH_COOKIE_NAME, computeAuthCookieValue } from "@/lib/authCookie";

// Nota: en Next.js 16 el fichero "middleware.ts" está deprecado en favor de
// "proxy.ts" (mismo mecanismo, nuevo nombre) — ver node_modules/next/dist/docs/
// 01-app/03-api-reference/03-file-conventions/proxy.md. Se usa proxy.ts aquí
// a propósito en vez del middleware.ts pedido originalmente.

export function proxy(request: NextRequest) {
  const appPin = process.env.APP_PIN;
  const cookie = request.cookies.get(AUTH_COOKIE_NAME);

  if (appPin && cookie?.value === computeAuthCookieValue(appPin)) {
    return NextResponse.next();
  }

  return NextResponse.redirect(new URL("/login", request.url));
}

export const config = {
  matcher: ["/((?!login|_next/static|_next/image|favicon.ico).*)"],
};
