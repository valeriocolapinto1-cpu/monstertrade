# MonsterTrade

App personale di analisi tecnica e sentiment che propone trade su ETF a leva e crypto, con etichetta di rischio e rischio per trade limitato all'1% del capitale. Strumento informativo, non consulenza.

Piano: [`docs/PIANO.md`](docs/PIANO.md) · Regole di lavoro: [`CLAUDE.md`](CLAUDE.md) · Sicurezza: [`docs/sicurezza.md`](docs/sicurezza.md)

## Struttura

- `backend/` FastAPI (Python 3.12, uv)
- `frontend/` Next.js, TypeScript, Tailwind, shadcn/ui
- `docs/` piano, decisioni, sicurezza

## Avvio in locale

```bash
cp .env.example .env            # compila le chiavi, mai committare .env

cd backend && uv sync && uv run uvicorn app.main:app --reload     # http://localhost:8000/health
cd frontend && npm ci && npm run dev                              # http://localhost:3000
```

## Controlli

```bash
cd backend && uv run ruff check . && uv run mypy && uv run pytest
cd frontend && npm run lint && npm run typecheck && npm test
```
