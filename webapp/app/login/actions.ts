"use server";

import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { AUTH_COOKIE_NAME, AUTH_COOKIE_MAX_AGE_SECONDS, computeAuthCookieValue } from "@/lib/authCookie";

export async function login(formData: FormData) {
  const pin = String(formData.get("pin") ?? "");
  const appPin = process.env.APP_PIN;

  if (!appPin || pin !== appPin) {
    redirect("/login?error=1");
  }

  const cookieStore = await cookies();
  cookieStore.set(AUTH_COOKIE_NAME, computeAuthCookieValue(appPin), {
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: "lax",
    maxAge: AUTH_COOKIE_MAX_AGE_SECONDS,
    path: "/",
  });

  redirect("/");
}
