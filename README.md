# MonsterTrade

App personale di analisi tecnica e sentiment che propone trade su ETF a leva e crypto, con etichetta di rischio e rischio per trade limitato all'1% del capitale. Strumento informativo, non consulenza.

Piano: [`docs/PIANO.md`](docs/PIANO.md) · Regole di lavoro: [`CLAUDE.md`](CLAUDE.md) · Sicurezza: [`docs/sicurezza.md`](docs/sicurezza.md)

## Struttura

- `backend/` FastAPI (Python 3.12, uv)
- `frontend/` Next.js, TypeScript, Tailwind, shadcn/ui
- `docs/` piano, decisioni, sicurezza

## Avvio in locale

Serve un Postgres (locale o ospitato); l'URL va in `DATABASE_URL`.

```bash
cp .env.example .env            # compila le chiavi, mai committare .env

cd backend && uv sync
uv run alembic upgrade head                    # crea le tabelle
uv run python -m app.jobs.prices update        # storico al primo avvio, poi incrementale
uv run python -m app.jobs.prices quality       # rapporto di qualità (exit 1 se ci sono buchi)
uv run python -m app.jobs.indicators           # indicatori per il motore dei segnali
uv sync --extra ml && uv run python -m app.jobs.sentiment --history   # sentiment con FinBERT
uv run python -m app.jobs.signals              # score, segnali ed etichette di rischio
uv run python -m app.jobs.backtest             # backtest strategie semplici e score
uv run uvicorn app.main:app --reload           # http://localhost:8000/health

cd frontend && npm ci && npm run dev           # http://localhost:3000
```

## Deploy

- **API**: Render, dal blueprint `render.yaml` (imposta `DATABASE_URL` e `CORS_ORIGINS` nel pannello).
- **Frontend**: Vercel con cartella `frontend` e variabile `API_URL` (URL dell'API, letto solo lato server).
- **Job pianificati**: `.github/workflows/data.yml` (prezzi, indicatori, score) ogni 30 minuti e `sentiment.yml` (FinBERT) ogni 2 ore; si attivano quando nei secrets del repository c'è `DATABASE_URL`.

Dettagli: [`docs/dati.md`](docs/dati.md) · [`docs/indicatori-backtest.md`](docs/indicatori-backtest.md) · [`docs/sentiment-score.md`](docs/sentiment-score.md)

## Controlli

```bash
cd backend && uv run ruff check . && uv run mypy && uv run pytest
cd frontend && npm run lint && npm run typecheck && npm test
```
