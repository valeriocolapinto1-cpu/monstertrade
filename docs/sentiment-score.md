# Sentiment e score (Fase 3)

## Sentiment

| Fonte | Chiave | Cosa si raccoglie | Come diventa un numero |
| --- | --- | --- | --- |
| Google News RSS | no | Titoli degli ultimi 3 giorni per indice e crypto | FinBERT in locale |
| StockTwits | no | Messaggi recenti (SPY, QQQ, SOXX, BTC.X, ETH.X, SOL.X) | Etichetta dell'utente (Bullish/Bearish) se presente, altrimenti FinBERT |
| Alternative.me Fear and Greed | no | Indice giornaliero crypto, storico dal 2018 | (valore − 50) / 50 |
| Finnhub | `FINNHUB_API_KEY` | Notizie per ETF | FinBERT |
| Reddit | `REDDIT_CLIENT_ID`, `REDDIT_CLIENT_SECRET` | Titoli dei post (r/wallstreetbets, r/investing, r/CryptoCurrency, …) | FinBERT |

Niente X/Twitter. Il sentiment si salva per sottostante, giorno e fonte (`sentiment`); gli strumenti a leva usano quello del sottostante.

FinBERT (`ProsusAI/finbert`, revisione fissata `0bc2ac1`) gira solo nel job `sentiment.yml` su GitHub Actions, con il modello in cache: l'API su Render non installa le librerie ML (extra `ml`). Lo score del testo è P(positivo) − P(negativo). Tutti gli XML sono letti con `defusedxml`.

## Score

Per ogni strumento e orizzonte (day trading su 15 minuti, swing su giornaliero, lungo periodo su settimanale) lo score va da −100 a +100 ed è la media pesata di quattro componenti, ognuna media di segnali elementari in [−1, 1]:

| Componente | Segnali |
| --- | --- |
| Trend | prezzo rispetto alla media lenta, media veloce contro lenta, istogramma MACD, ADX con ±DI |
| Momentum | RSI rispetto a 50, RSI estremo (segnale contrario), stocastico, rendimento recente |
| Volumi | OBV che conferma o diverge, prezzo rispetto al VWAP (day trading) |
| Sentiment | media pesata delle fonti negli ultimi 1, 3 o 14 giorni, sentiment estremo (segnale contrario) |

Il sentiment di un giorno entra solo dal giorno dopo (nessun lookahead); oltre una settimana senza dati non conta. Le componenti senza dati (ad esempio i volumi degli indici) non pesano. Ogni score salva componenti, segnali a favore e contrari all'acquisto ed etichetta di rischio (`signals`). Per gli ETF short lo score è quello del sottostante con il segno invertito.

### Etichetta di rischio

Regole in `backend/app/analysis/risk_label.py`, testate caso per caso: leva, ETF short, settore ristretto (semiconduttori), crypto minori (SOL), volatilità (ATR %) rispetto alla mediana dell'ultimo anno, orizzonte day trading con leva 3x, distanza dello stop, notizie imminenti, correlazione con le posizioni aperte.

## Backtest dello score (criterio della Fase 3)

Regola: in posizione quando lo score supera la soglia; stessi costi ed esecuzione all'apertura successiva delle strategie semplici della Fase 2.

**Con i pesi iniziali del piano (40/30/15/15) il criterio non era soddisfatto**: Sharpe medio nello swing 0,32 contro 0,45 delle strategie semplici. Momentum e volumi cambiano spesso segno e moltiplicano le operazioni, e i costi se le mangiano.

Correzione, senza adattarsi ai dati: cinque varianti fissate in anticipo, scelta sulla **prima metà** dello storico, verifica sulla **seconda metà**.

| Variante | Swing 1ª metà | Lungo 1ª metà | Swing 2ª metà | Lungo 2ª metà |
| --- | --- | --- | --- | --- |
| Strategie semplici (riferimento) | 0,40 | 0,35 | 0,36 | 0,43 |
| Base 40/30/15/15, soglia 20 | 0,34 | 0,36 | 0,24 | 0,48 |
| Isteresi (entra > 20, esce < 0) | 0,39 | 0,37 | 0,38 | 0,56 |
| Trend 60/20/10/10, isteresi | 0,47 | 0,35 | 0,48 | 0,54 |
| Trend 60/20/10/10, isteresi, media a 5 | 0,55 | 0,37 | 0,52 | 0,44 |
| **Trend 80, sentiment 20, isteresi** (adottata) | **0,48** | **0,47** | **0,46** | **0,49** |

La variante adottata è la migliore in media sulla prima metà e batte le strategie semplici anche sulla seconda.

**Risultato su tutto lo storico (criterio soddisfatto)**:

| Orizzonte | Sharpe score | Sharpe strategie semplici (media) | Batte la media | Batte la migliore |
| --- | --- | --- | --- | --- |
| Swing | 0,50 | 0,45 | 9 su 14 | 3 su 14 |
| Lungo periodo | 0,52 | 0,47 | 9 su 14 | 7 su 14 |
| Day trading | −4,15 | −10,60 | 13 su 14 | 8 su 14 |

Nel day trading lo score perde meno ma resta negativo: i costi rendono il day trading sconsigliabile con questo capitale.

Limiti: lo storico del sentiment esiste solo per le crypto (Fear and Greed dal 2018); per gli indici il backtest misura la parte tecnica. Momentum e volumi hanno peso zero ma restano visibili tra i segnali a favore e contrari.
