import { login } from "./actions";

export default async function LoginPage({
  searchParams,
}: {
  searchParams: Promise<{ error?: string }>;
}) {
  const { error } = await searchParams;

  return (
    <main className="page login-page">
      <form action={login} className="card login-card">
        <h1>cazapisos</h1>
        <label htmlFor="pin">Código de acceso</label>
        <input id="pin" name="pin" type="password" autoFocus required autoComplete="off" />
        <button type="submit">Entrar</button>
        {error && <p className="error">Código incorrecto.</p>}
      </form>
    </main>
  );
}
