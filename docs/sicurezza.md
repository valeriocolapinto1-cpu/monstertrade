# Sicurezza

## Controlli obbligatori in CI

| Controllo | Backend | Frontend |
| --- | --- | --- |
| Lint | ruff | eslint (zero avvisi) |
| Type check | mypy (strict) | tsc |
| Test | pytest | vitest |
| Audit dipendenze | pip-audit (tutte, `--strict`) | `npm audit`: produzione a qualsiasi livello, sviluppo a livello critico |
| Analisi statica di sicurezza | bandit, CodeQL `security-extended` | CodeQL `security-extended` |
| Scansione dei segreti | gitleaks su tutta la storia | gitleaks su tutta la storia |

Le action sono fissate per SHA del commit; Dependabot propone gli aggiornamenti ogni settimana.

### Eccezione documentata sull'audit npm

`braces` (GHSA-vfj7-8cjw-p6xm, alta) non ha versione corretta ed entra solo tramite strumenti di sviluppo (`eslint-config-next`, CLI `shadcn`): non finisce nel bundle servito. Per questo l'audit completo blocca a livello critico, quello di produzione a qualsiasi livello. Da rivedere quando esce una correzione.

## Protezione di `main` (da attivare una volta nelle impostazioni GitHub)

Settings → Rules → Rulesets → New branch ruleset:

- Target: branch di default (`main`), Enforcement: Active.
- Require a pull request before merging; merge consentito: Squash.
- Require status checks to pass, con questi controlli:
  - `Backend (lint, type check, test, audit, SAST)`
  - `Frontend (lint, type check, test, audit, build)`
  - `Scansione dei segreti (gitleaks)`
  - `Analisi statica di sicurezza (python)`
  - `Analisi statica di sicurezza (javascript-typescript)`
  - `Analisi statica di sicurezza (actions)`
- Block force pushes; Restrict deletions.

In Settings → Code security attivare anche Secret scanning e Push protection.

## Segreti

Solo in variabili d'ambiente lato server (Render, GitHub Actions secrets). Mai nel browser, nel repository o nei log; nel backend sono `SecretStr`, quindi mascherati in `repr` e serializzazione.

## Accesso e conto reale (Fase 5)

- App protetta da password (hash scrypt) e sessione firmata `HttpOnly`/`SameSite=Strict`; API raggiungibile solo con il segreto condiviso, verificato in un middleware prima di qualsiasi altra operazione.
- Trading 212 in sola lettura: chiave con soli permessi di lettura, solo richieste GET, errori che non riportano mai credenziali. Dettagli in `docs/trading212.md`.
- Ordini (passo C): disattivati di default, chiave di trading separata, blocco totale attivo se mai disattivato, conferma esplicita con codice firmato a scadenza (90 s) per ogni ordine, limiti rigidi ricontrollati lato server, registro scritto prima di ogni invio, nessun nuovo tentativo automatico. Le scritture passano solo dal server del frontend (sessione, stessa origine, JSON validato) e dall'API con segreto condiviso. Test dedicati in `backend/tests/test_orders.py` e `frontend/src/lib/orders.test.ts`.
