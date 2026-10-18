# MonsterTrade

App personale di analisi tecnica e sentiment che propone trade su ETF a leva e crypto, con etichetta di rischio e rischio per trade limitato all'1% del capitale. **Strumento informativo, non consulenza.** Al momento è una simulazione: nessun ordine viene inviato al broker.

Piano: [`docs/PIANO.md`](docs/PIANO.md) · Regole di lavoro: [`CLAUDE.md`](CLAUDE.md) · Sicurezza: [`docs/sicurezza.md`](docs/sicurezza.md) · Decisioni: [`docs/decisioni.md`](docs/decisioni.md)

| Fase | Stato | Dettagli |
| --- | --- | --- |
| 1. Dati e grafici | completata | [`docs/dati.md`](docs/dati.md) |
| 2. Indicatori e backtesting | completata | [`docs/indicatori-backtest.md`](docs/indicatori-backtest.md) |
| 3. Sentiment e score | completata | [`docs/sentiment-score.md`](docs/sentiment-score.md) |
| 4. Simulazione e rischio | completata, simulazione da avviare | [`docs/simulazione.md`](docs/simulazione.md) |
| 5. Trading 212 | passo B (lettura del conto) completato; ordini non implementati | [`docs/trading212.md`](docs/trading212.md) |

## Struttura

- `backend/` FastAPI, pandas, vectorbt, FinBERT (Python 3.12, uv)
- `frontend/` Next.js, TypeScript, Tailwind, shadcn/ui, Lightweight Charts, PWA
- `docs/` piano, decisioni, sicurezza, documentazione delle fasi
- `.github/workflows/` CI di sicurezza e job pianificati

## Installazione

Servono Python 3.12 con [uv](https://docs.astral.sh/uv/), Node.js 22 e un database Postgres (locale, Supabase, Neon…).

```bash
cp .env.example .env            # compila i valori; .env non va mai nel repository

cd backend
uv sync                         # dipendenze (aggiungi --extra ml per FinBERT)
uv run alembic upgrade head     # crea le tabelle

cd ../frontend
npm ci
```

## Variabili d'ambiente

| Variabile | Dove | Obbligatoria | Note |
| --- | --- | --- | --- |
| `DATABASE_URL` | backend, job | sì | URL Postgres |
| `CORS_ORIGINS` | backend | no | Origini ammesse, in JSON |
| `CAPITAL_EUR` | backend, job | no | 500-2.000, default 1.000 |
| `RISK_PER_TRADE`, `MAX_DAILY_LOSS`, `MAX_OPEN_POSITIONS`, `MAX_LEV3_EXPOSURE` | backend, job | no | Si possono solo stringere rispetto al piano |
| `TWELVE_DATA_API_KEY` | job | no | Senza chiave si usa `yfinance` |
| `FINNHUB_API_KEY`, `REDDIT_CLIENT_ID`, `REDDIT_CLIENT_SECRET` | job sentiment | no | Fonti aggiuntive di sentiment |
| `NTFY_TOPIC` | job trading | no | Notifiche delle nuove proposte |
| `API_URL` | frontend (server) | sì in produzione | URL dell'API, mai esposto al browser |
| `API_SHARED_SECRET` | backend e frontend | sì in produzione | Stesso valore sui due lati; senza, l'API rifiuta tutto |
| `APP_PASSWORD_HASH`, `SESSION_SECRET` | frontend | sì in produzione | Password dell'app (`node frontend/scripts/hash-password.mjs`) e firma delle sessioni |
| `T212_API_KEY`, `T212_API_SECRET`, `T212_ENV` | backend, job trading | no | Trading 212 in sola lettura (`live` o `demo`) |

Tutte le chiavi restano lato server: nei secrets di GitHub Actions e nelle variabili di Render/Vercel.

## Comandi

```bash
cd backend
uv run python -m app.jobs.prices update        # prezzi: storico al primo avvio, poi incrementale
uv run python -m app.jobs.prices quality       # qualità dei dati (exit 1 se ci sono buchi)
uv run python -m app.jobs.indicators           # indicatori
uv run --extra ml python -m app.jobs.sentiment # sentiment con FinBERT (--history per lo storico)
uv run python -m app.jobs.signals              # score, segnali ed etichette di rischio
uv run python -m app.jobs.trading              # proposte e simulazione
uv run python -m app.jobs.backtest             # backtest strategie semplici e score
uv run uvicorn app.main:app --reload           # API su http://localhost:8000

cd frontend
npm run dev                                    # interfaccia su http://localhost:3000
```

Controlli (gli stessi della CI):

```bash
cd backend && uv run ruff check . && uv run mypy && uv run pytest     # TEST_DATABASE_URL per i test sul DB
cd frontend && npm run lint && npm run typecheck && npm test && npm run build
```

## Deploy

- **API**: Render, dal blueprint `render.yaml` (imposta `DATABASE_URL` e `CORS_ORIGINS`).
- **Frontend**: Vercel, cartella `frontend`, variabile `API_URL`.
- **Job pianificati**: `data.yml` ogni 30 minuti (prezzi, indicatori, score, proposte, simulazione) e `sentiment.yml` ogni 2 ore (FinBERT). Partono solo se nei secrets c'è `DATABASE_URL`.

## Come fermare tutto in sicurezza

L'app non invia ordini, quindi fermarla non lascia posizioni reali aperte. In ordine:

0. **Trading 212**: revoca la chiave API dall'app Trading 212 (Impostazioni → API): l'accesso al conto si interrompe subito, qualunque cosa succeda all'app.

1. **Job pianificati**: GitHub → Actions → "Aggiornamento dati" e "Sentiment" → menu `…` → *Disable workflow*. In alternativa togli il secret `DATABASE_URL`: i job si saltano da soli.
2. **API**: Render → servizio `monstertrade-api` → *Suspend*.
3. **Frontend**: Vercel → progetto → *Settings* → *Pause* (o elimina il deployment).
4. **Dati**: il database resta intatto; per ripartire basta riattivare i passi sopra.

In locale: `Ctrl+C` su `uvicorn` e `npm run dev`.
