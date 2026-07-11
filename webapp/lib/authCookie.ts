import crypto from "crypto";

// No "server-only": este módulo importa el módulo nativo "crypto", que ya no
// existe en el navegador, así que solo puede usarse desde código de servidor
// (proxy.ts y app/login/actions.ts).

export const AUTH_COOKIE_NAME = "cazapisos_auth";
export const AUTH_COOKIE_MAX_AGE_SECONDS = 60 * 60 * 24 * 180; // 180 días

// La cookie guarda "<group_id>.<firma>": el group_id activo (no es secreto,
// solo identifica la fila de `groups`) más una firma HMAC que demuestra que
// el servidor lo emitió — así un valor de cookie manipulado a mano (para
// intentar entrar en otro grupo sin saber su PIN) no pasa la verificación.
// Se firma con SESSION_SECRET, un secreto de firma independiente de
// cualquier PIN de login (ver .env.local.example) — APP_PIN lo conocen el
// amigo y su mujer para entrar, así que usarlo también como clave HMAC
// dejaría en teoría fabricar una cookie válida para otro grupo a quien
// conozca APP_PIN y adivine su group_id (un UUID).
function sign(groupId: string): string {
  const secret = process.env.SESSION_SECRET ?? "";
  return crypto.createHmac("sha256", secret).update(groupId).digest("hex");
}

export function computeSessionCookieValue(groupId: string): string {
  return `${groupId}.${sign(groupId)}`;
}

// Devuelve el group_id si la cookie es válida (firma correcta), o null si
// falta, tiene un formato inesperado, o la firma no coincide.
export function verifySessionCookieValue(value: string | undefined): string | null {
  if (!value) return null;

  const separatorIndex = value.lastIndexOf(".");
  if (separatorIndex <= 0) return null;

  const groupId = value.slice(0, separatorIndex);
  const signature = value.slice(separatorIndex + 1);

  const expected = sign(groupId);
  const actual = Buffer.from(signature);
  const expectedBuf = Buffer.from(expected);
  if (actual.length !== expectedBuf.length || !crypto.timingSafeEqual(actual, expectedBuf)) {
    return null;
  }

  return groupId;
}
