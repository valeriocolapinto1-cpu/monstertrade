import "server-only";

/** Avvio manuale dell'aggiornamento dati (workflow GitHub Actions `data.yml`). */

const API = "https://api.github.com";
const WORKFLOW = "data.yml";
const REPO_PATTERN = /^[\w.-]+\/[\w.-]+$/;

export interface RefreshStatus {
  configured: boolean;
  status: "in_corso" | "completato" | "fallito" | "sconosciuto";
  started_at: string | null;
  finished_at: string | null;
}

function config(): { token: string; repo: string } | null {
  const token = process.env.GITHUB_DISPATCH_TOKEN?.trim();
  const repo = (process.env.GITHUB_REPOSITORY ?? "valeriocolapinto1-cpu/monstertrade").trim();
  if (!token || !REPO_PATTERN.test(repo)) return null;
  return { token, repo };
}

function headers(token: string): Record<string, string> {
  return {
    Authorization: `Bearer ${token}`,
    Accept: "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
    "User-Agent": "monstertrade",
  };
}

export async function refreshStatus(): Promise<RefreshStatus> {
  const cfg = config();
  const empty: RefreshStatus = { configured: false, status: "sconosciuto", started_at: null, finished_at: null };
  if (!cfg) return empty;
  const res = await fetch(`${API}/repos/${cfg.repo}/actions/workflows/${WORKFLOW}/runs?per_page=1`, {
    headers: headers(cfg.token),
    cache: "no-store",
    signal: AbortSignal.timeout(10_000),
  }).catch(() => null);
  if (!res?.ok) return { ...empty, configured: true };
  const data = (await res.json()) as {
    workflow_runs?: { status?: string; conclusion?: string | null; run_started_at?: string; updated_at?: string }[];
  };
  const run = data.workflow_runs?.[0];
  if (!run) return { ...empty, configured: true };
  const running = run.status !== "completed";
  return {
    configured: true,
    status: running ? "in_corso" : run.conclusion === "success" ? "completato" : "fallito",
    started_at: run.run_started_at ?? null,
    finished_at: running ? null : (run.updated_at ?? null),
  };
}

/** Avvia l'aggiornamento; se uno è già in corso non ne avvia un altro. */
export async function triggerRefresh(): Promise<{ ok: boolean; detail: string }> {
  const cfg = config();
  if (!cfg) return { ok: false, detail: "Aggiornamento manuale non configurato: manca GITHUB_DISPATCH_TOKEN su Vercel" };
  const current = await refreshStatus();
  if (current.status === "in_corso") return { ok: true, detail: "Aggiornamento già in corso" };
  const res = await fetch(`${API}/repos/${cfg.repo}/actions/workflows/${WORKFLOW}/dispatches`, {
    method: "POST",
    headers: { ...headers(cfg.token), "Content-Type": "application/json" },
    body: JSON.stringify({ ref: "main" }),
    cache: "no-store",
    signal: AbortSignal.timeout(10_000),
  }).catch(() => null);
  if (res?.status === 204) return { ok: true, detail: "Aggiornamento avviato: circa 3-4 minuti" };
  if (res?.status === 401 || res?.status === 403 || res?.status === 404) {
    return { ok: false, detail: "Token GitHub non valido o senza permesso Actions (lettura e scrittura)" };
  }
  return { ok: false, detail: "GitHub non raggiungibile: riprova tra poco" };
}
