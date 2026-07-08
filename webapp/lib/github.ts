import "server-only";

// No hace falta ocultar owner/repo en variables de entorno: no son datos sensibles.
const OWNER = "Rafailla";
const REPO = "cazapisos";
const WORKFLOW_FILE = "scrape.yml";

export async function triggerScrapeWorkflow(): Promise<{ error?: string }> {
  const token = process.env.GITHUB_TOKEN;
  if (!token) {
    return { error: "Falta GITHUB_TOKEN. Copia .env.local.example a .env.local y rellénalo." };
  }

  const response = await fetch(
    `https://api.github.com/repos/${OWNER}/${REPO}/actions/workflows/${WORKFLOW_FILE}/dispatches`,
    {
      method: "POST",
      headers: {
        Authorization: `Bearer ${token}`,
        Accept: "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
      },
      body: JSON.stringify({ ref: "main" }),
    }
  );

  if (!response.ok) {
    const body = await response.text();
    return { error: `GitHub respondió ${response.status}: ${body || response.statusText}` };
  }

  return {};
}
