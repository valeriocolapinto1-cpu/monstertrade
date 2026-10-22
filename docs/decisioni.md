# Decisioni

| Data | Decisione | Motivo |
| --- | --- | --- |
| 2026-10-18 | Deploy: frontend su Vercel, API FastAPI su Render (piano gratuito), job pesanti su GitHub Actions pianificate, DB su Supabase | I piani gratuiti con 512 MB di RAM non reggono FinBERT; con il repository pubblico i minuti di Actions sono gratuiti. Cloudflare scartato: Workers Python non esegue pandas/vectorbt/FinBERT e D1 non è Postgres |
| 2026-10-18 | Repository pubblico | Protezione di `main`, CodeQL e scansione dei segreti di GitHub gratuite e applicate |
| 2026-10-18 | Universo iniziale: lista completa (vedi sotto) | Scelta dell'utente |
| 2026-10-18 | Accento `#00A7E1` ricavato dal logo Trading 212 | Il sito di riferimento blocca i browser automatici con un captcha; palette e densità definite in `frontend/src/styles/tokens.css` |

## Universo iniziale (da verificare ticker e disponibilità su Trading 212 in Fase 1)

| Gruppo | Strumenti | Segnale calcolato su |
| --- | --- | --- |
| Indici | S&P 500, Nasdaq 100, PHLX Semiconductor (SOX) | Indice stesso |
| Leva long | S&P 500 3x, Nasdaq 100 3x, Nasdaq 100 2x, semiconduttori 3x | Indice sottostante × fattore |
| Leva short | S&P 500 -3x, Nasdaq 100 -3x | Indice sottostante × fattore |
| Crypto | BTC, ETH, SOL | Binance (coppie USDT) |
| ETP crypto | ETP fisici BTC ed ETH | Sottostante crypto |

## Capitale minimo 50 € (22 ottobre 2026)

L'utente opera con un capitale reale di 50 €. Il minimo di `CAPITAL_EUR` passa da 500 a 50 € e il minimo per posizione (`MIN_ORDER_EUR`) da 10 a 1 €, sfruttando le frazioni di Trading 212. Tutte le altre regole restano invariate: rischio 1% per trade (0,50 € con 50 €), perdita giornaliera massima 3%, massimo 3 posizioni, massimo 30% in leva 3x (15 €). Con posizioni di pochi euro ogni proposta deve comunque risultare conveniente dopo spread e cambio.
