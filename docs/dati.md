# Dati di mercato (Fase 1)

## Fonti

| Strumento | Principale | Riserva | Note |
| --- | --- | --- | --- |
| Indici (S&P 500, Nasdaq 100, SOX) | Twelve Data (se `TWELVE_DATA_API_KEY` è impostata) | `yfinance` | Senza chiave si usa direttamente `yfinance` |
| Crypto (BTC, ETH, SOL) | Binance (`data-api.binance.vision`, senza chiave) | `yfinance` | `api.binance.com` risponde 451 da alcune regioni cloud |
| ETF a leva, ETP crypto | Serie sintetica dal sottostante | — | Vedi sotto |

Ogni fonte implementa `PriceSource` (`backend/app/data/sources/base.py`); il registro prova le fonti in ordine, salta quelle non configurate, rispetta i limiti di richieste (token bucket per fonte) e tiene una cache su disco delle risposte.

## Timeframe e conservazione

- `1d`: dal 2000 (o dalla quotazione) a oggi.
- `15m` e `5m`: ultimi 60 giorni (limite di Yahoo); i dati più vecchi vengono cancellati per restare nel piano gratuito del database.
- `1w`: calcolato al volo dalle giornaliere (settimana da lunedì).

Le giornaliere hanno come orario la mezzanotte UTC della data di sessione; l'intraday l'inizio della candela in UTC. Le candele non ancora chiuse non vengono salvate.

## Serie sintetiche degli strumenti a leva

```
r_strumento = L × r_sottostante + (1 − L) × tasso_finanziamento − TER
```

con ribilanciamento giornaliero, costi maturati sui giorni di calendario, tasso di finanziamento `FUNDING_RATE` (4% annuo di default). Il livello vale 100 il 2 gennaio 2025. L'intraday riparte ogni giorno dalla chiusura precedente, coerente con il giornaliero. Lo strumento non può scendere sotto zero.

Limiti: niente spread dello swap, tracking error, cambio valuta e orari della borsa europea di quotazione. Prima di operare vanno verificati ticker e prezzi reali su Trading 212.

## Controllo di qualità

`python -m app.jobs.prices quality` (ed endpoint `/api/quality`) verifica per ogni strumento e timeframe:

- **buchi**: confronto con il calendario NYSE (festività e mezze giornate incluse) o con il calendario continuo delle crypto, fino all'ultima candela attesa;
- **duplicati** e **valori impossibili** (prezzi non positivi, massimo sotto il minimo, apertura o chiusura fuori dal range);
- **anomalie**: rendimenti oltre 12 deviazioni robuste e oltre il 10%, segnalati per verifica (non sono errori: ad esempio 16 marzo 2020).

## Criterio di passaggio della Fase 1 (18 ottobre 2026)

Tutti i 14 strumenti, tutti i timeframe salvati: **0 candele mancanti, 0 duplicati, 0 valori non validi**. Anomalie segnalate, tutte riconducibili a eventi reali: ottobre 2008, marzo 2020, gennaio 2001 (Nasdaq), novembre 2022 (crollo di FTX su SOL), aperture in gap del 3x sui semiconduttori.
