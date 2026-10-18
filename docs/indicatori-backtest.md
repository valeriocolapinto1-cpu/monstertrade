# Indicatori e backtest (Fase 2)

## Indicatori

Calcolati in `backend/app/analysis/indicators.py` solo con dati passati: il valore alla candela *t* non cambia aggiungendo candele future (test `test_no_lookahead`).

| Gruppo | Indicatori |
| --- | --- |
| Trend | SMA ed EMA 20/50/200, MACD (12, 26, 9), ADX (14) con +DI e −DI |
| Momentum | RSI (14, medie di Wilder), Stocastico (14, 3, 3) |
| Volatilità | Bande di Bollinger (20, 2), ATR (14) e ATR % |
| Volumi | OBV, VWAP intraday (assenti dove non ci sono volumi: indici e serie sintetiche) |
| Livelli | Supporti e resistenze (pivot a 5 candele raggruppati entro 0,5 ATR), ritracciamenti di Fibonacci (ultime 120 candele) |
| Rischio | Drawdown massimo, Sharpe, correlazione dei rendimenti (90 giorni), volatilità realizzata (20) |
| Leva | Volatilità realizzata del sottostante e decadimento stimato `(L² − L) / 2 × σ²` |

Verifica: RSI contro l'esempio di Wilder pubblicato da StockCharts; SMA, EMA, MACD, RSI, ATR, Bollinger, Stocastico, OBV e ADX contro la libreria `ta` (dopo il periodo di riscaldamento).

Ogni indicatore ha nell'interfaccia una scheda in italiano con **cosa misura**, **come si legge**, **quando inganna** (`frontend/src/lib/indicator-cards.ts`). Nel database (`indicators`) si salvano le ultime 500 giornaliere e 300 candele intraday per il motore dei segnali; i grafici li calcolano al volo.

## Backtest

`python -m app.jobs.backtest` (o `/api/backtest`) con vectorbt.

- **Niente lookahead**: segnale alla chiusura della candela *t*, operazione all'apertura di *t+1*.
- **Costi per lato**: metà spread stimato (0,03% indici, 0,10% ETF a leva, 0,25% crypto, 0,20% ETP crypto) più il cambio valuta 0,15% di Trading 212 sugli strumenti non in euro.
- **Solo posizioni lunghe**; nel day trading sugli strumenti USA la posizione si chiude a fine sessione.
- **Nessuna ottimizzazione**: parametri fissi e classici, per non adattarsi al passato.

| Orizzonte | Dati | Strategie |
| --- | --- | --- |
| Day trading | 15 minuti, ultimi 60 giorni | Incrocio EMA 20/50; RSI > 50 e MACD positivo |
| Swing | Giornaliero dal 2000 | Incrocio SMA 50/200; prezzo sopra SMA 200; momentum 3 mesi |
| Lungo periodo | Settimanale dal 2000 | Prezzo sopra SMA 40 settimane; momentum 12 mesi |

Ogni orizzonte include "compra e tieni" come riferimento.

### Risultati (18 ottobre 2026)

**Criterio di passaggio soddisfatto**: 58 strategie su 98 positive dopo i costi.

| Strumento | Strategia | Annuo | Drawdown max | Compra e tieni (annuo / drawdown) |
| --- | --- | --- | --- | --- |
| Nasdaq 100 2x | Prezzo sopra SMA 200 | +13,7% | −43% | +3,4% / −99% |
| Nasdaq 100 3x | Prezzo sopra SMA 200 | +12,5% | −67% | −7,7% / −100% |
| S&P 500 3x | Incrocio SMA 50/200 | +5,8% | −79% | −1,4% / −99% |
| Nasdaq 100 | Incrocio SMA 50/200 | +10,4% | −28% | +8,0% / −83% |
| Bitcoin | Prezzo sopra SMA 40 settimane | +35,5% | −48% | +38,4% / −83% |

Cosa dicono i numeri:

- Sugli **ETF a leva long** un filtro di trend trasforma risultati disastrosi (il compra e tieni sul 3x azzera il capitale nel 2000-2002 e nel 2008) in rendimenti positivi: conferma che la leva va usata solo con un filtro di trend e non tenuta a lungo.
- Gli **ETF short** perdono con tutte le strategie long: il decadimento e la tendenza rialzista di lungo periodo li rendono adatti solo a operazioni brevi in mercati ribassisti.
- Sulle **crypto** i filtri di trend riducono molto il drawdown, ma non battono sempre il compra e tieni in rendimento.
- Nel **day trading** nessuna strategia è positiva: con 0,15% di cambio valuta per lato e lo spread, i costi superano il vantaggio su 60 giorni. Per il day trading conviene preferire strumenti in euro e operare raramente.

Limiti: serie a leva sintetiche dal 2000 (i prodotti reali sono più recenti), indici di prezzo senza dividendi, nessun interesse sulla liquidità quando si è fuori dal mercato.
