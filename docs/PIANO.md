# Piano: app di analisi e proposte di trade

Webapp personale che unisce prezzi, indicatori tecnici e sentiment social per proporre trade su ETF a leva e crypto, con etichetta di rischio e rischio per trade limitato all'1% del capitale. Data: 18 ottobre 2026.

## Obiettivi e vincoli

L'app propone trade con etichetta di rischio; la decisione finale resta all'utente, almeno fino a mesi di prova in simulazione.

| Voce | Scelta |
| --- | --- |
| Uso | Personale, nessuna consulenza ad altri |
| Capitale | 50 – 2.000 € (minimo abbassato da 500, vedi `docs/decisioni.md`) |
| Rischio per trade | Circa 1% del capitale (5 – 20 € a trade) |
| Strumenti | ETF a leva su indici USA e settori (tech, semiconduttori), ETF short/inversi, crypto e ETP crypto |
| Orizzonti | Day trading, swing (giorni/settimane), lungo periodo |
| Broker | Trading 212, prima solo suggerimenti, poi ordini automatici |
| Stack | Backend Python (FastAPI), interfaccia Next.js, Postgres |

Con un capitale così piccolo commissioni e spread pesano molto: l'app deve segnalare quando un trade non conviene dopo i costi. Gli ETF a leva perdono valore nei mercati laterali (decadimento da volatilità): adatti a posizioni brevi, non a un lungo periodo senza controllo.

## Architettura

Tre livelli:

1. **Fonti dati**: Prezzi (Twelve Data, Binance, yfinance); Sentiment (Finnhub, Reddit, Fear and Greed).
2. **Backend Python (FastAPI)**: Raccolta dati (job pianificati, sentiment FinBERT) → Indicatori e score (per strumento e orizzonte) → Rischio e proposte (stop, dimensione, etichetta).
3. **Database e interfaccia**: Postgres (Supabase) con prezzi, segnali, diario; interfaccia Next.js come PWA; Trading 212 (lettura portafoglio, ordini in fase C).

Flussi: le fonti alimentano la raccolta dati; il backend scrive nel database; l'interfaccia legge dal database; la conferma dell'utente (tuo ok) passa al backend; solo il backend invia ordini a Trading 212. La chiave API di Trading 212 resta nel backend.

## Fonti dati gratuite

Due fonti per i prezzi e due per il sentiment, dietro un livello di astrazione sostituibile. I limiti dei piani gratuiti cambiano spesso: da controllare sulle pagine ufficiali prima di scrivere il codice.

| Dato | Fonte principale | Riserva | Nota |
| --- | --- | --- | --- |
| Prezzi azioni, ETF, indici | Twelve Data | Finnhub; `yfinance` per lo storico | `yfinance` è non ufficiale, può rompersi |
| Crypto | Binance API pubblica | CoinGecko | Binance è generosa e senza chiave per i dati di mercato |
| Notizie e sentiment azioni | Finnhub | Reddit (r/wallstreetbets, r/investing) | Sentiment calcolato in locale con FinBERT |
| Sentiment trader | StockTwits (se l'accesso API è aperto) | Google Trends | Da verificare: accesso API a StockTwits limitato in passato |
| Sentiment crypto | Alternative.me Fear and Greed | Reddit (r/CryptoCurrency) | Indice giornaliero, gratuito |

Punto critico: gli ETF a leva europei venduti su Trading 212 (quotati su borse europee) spesso non sono coperti bene dai piani gratuiti, che puntano sui titoli USA. Soluzione: analizzare l'indice sottostante (S&P 500, Nasdaq 100, semiconduttori) e applicare il segnale allo strumento a leva, tenendo conto del fattore (2x, 3x o -1x).

## Indicatori tecnici e come si leggono

Ogni indicatore ha nell'app una scheda con tre righe: cosa misura, come si legge, quando inganna. Nessun indicatore decide da solo: contano il numero di segnali concordi e quelli che discordano.

| Gruppo | Indicatore | Cosa misura | Come si legge | Quando inganna |
| --- | --- | --- | --- | --- |
| Trend | Medie mobili SMA/EMA (20, 50, 200) | Direzione media del prezzo | Prezzo sopra la 200: trend rialzista; incrocio 50/200: cambio di fase | In mercato laterale dà molti falsi segnali |
| Trend | MACD | Differenza tra due EMA | Incrocio con la linea segnale e istogramma che cresce: forza in aumento | Lento, segnala dopo che il movimento è partito |
| Trend | ADX | Forza del trend, non la direzione | Sopra 25: trend forte; sotto 20: mercato laterale | Non dice se si sale o si scende |
| Momentum | RSI (14) | Velocità dei rialzi contro i ribassi | Sopra 70 ipercomprato, sotto 30 ipervenduto | In trend forti resta a lungo in ipercomprato |
| Momentum | Stocastico | Posizione del prezzo nel range recente | Incroci sotto 20 e sopra 80 | Rumoroso sui tempi brevi |
| Volatilità | Bande di Bollinger | Distanza dalla media in deviazioni standard | Prezzo alla banda: estremo; bande strette: possibile esplosione | Il prezzo può restare sulla banda per giorni |
| Volatilità | ATR (14) | Ampiezza media del movimento giornaliero | Serve a fissare lo stop (ad esempio 1,5 × ATR) | Non dà direzione |
| Volumi | OBV | Volumi accumulati in base alla direzione | Divergenza con il prezzo: anticipa inversioni | Poco affidabile sulle crypto con volumi falsati |
| Volumi | VWAP | Prezzo medio pesato per i volumi del giorno | Sopra: pressione compratrice intraday | Utile solo nel day trading |
| Livelli | Supporti e resistenze, Fibonacci | Zone dove il prezzo ha reagito | Rimbalzo o rottura con volumi | Soggettivi, vanno calcolati con regole fisse |
| Rischio | Drawdown massimo, Sharpe, correlazione | Perdita massima dal picco, rendimento per unità di rischio, quanto si muovono insieme gli asset | Sharpe sopra 1 buono; correlazione alta = nessuna diversificazione | Si basano sul passato |

Per gli ETF a leva si aggiungono due indicatori propri: la **volatilità realizzata** dell'indice sottostante e il **decadimento stimato**, cioè quanto valore perderebbe lo strumento in un mercato laterale con quella volatilità.

## Motore dei segnali e etichetta di rischio

L'app calcola per ogni strumento uno score da -100 a +100 per ciascun orizzonte e propone un trade solo se lo score supera una soglia e il rischio calcolato resta entro i limiti dell'utente.

| Orizzonte | Dati | Indicatori principali | Peso del sentiment |
| --- | --- | --- | --- |
| Day trading | Candele da 5 e 15 minuti | VWAP, RSI, Stocastico, ATR, volumi | Basso (notizie del giorno) |
| Swing | Candele giornaliere | Medie mobili, MACD, ADX, Bollinger, supporti | Medio |
| Lungo periodo | Candele settimanali | Media a 200, drawdown, correlazione, trend dell'indice | Basso |

Lo score combina trend, momentum, volumi e sentiment con pesi iniziali semplici (ad esempio 40/30/15/15) da regolare con il backtesting. Ogni proposta mostra anche i segnali contrari, non solo quelli favorevoli.

**Etichetta di rischio** per ogni trade proposto:

| Etichetta | Quando si applica |
| --- | --- |
| Basso | Strumento senza leva, volatilità sotto la mediana, stop breve |
| Medio | Leva 2x o crypto maggiori, volatilità nella media |
| Alto | Leva 3x, ETF short o settore ristretto, volatilità sopra la mediana |
| Molto alto | Day trading con leva 3x, crypto minori, notizie importanti nelle prossime ore |

L'etichetta dipende da fattore di leva, volatilità (ATR in percentuale), orizzonte, correlazione con le posizioni già aperte e distanza dello stop. Se per rispettare l'1% di rischio la dimensione della posizione scende sotto il minimo acquistabile, il trade non viene proposto.

## Gestione del rischio

La dimensione di ogni posizione si calcola dallo stop, non dal desiderio di guadagno:

```
Posizione = (Capitale × 1%) / (Distanza dello stop in %)
```

Esempio: con 1.000 € di capitale il rischio massimo è 10 €; con uno stop al 5% sotto l'ingresso la posizione è di 200 €. Con uno strumento a leva 3x lo stop va misurato sul prezzo dello strumento stesso, che si muove tre volte più dell'indice.

Regole fisse applicate prima di proporre un trade:

- Perdita massima giornaliera del 3% del capitale: raggiunta, nessuna proposta fino al giorno dopo.
- Massimo 3 posizioni aperte e massimo 30% del capitale in strumenti a leva 3x.
- Niente nuovi trade su strumenti molto correlati a una posizione già aperta (ad esempio due ETF sul Nasdaq).
- Avviso quando un ETF a leva è tenuto più di alcuni giorni in mercato laterale (decadimento).
- Stop obbligatorio in ogni proposta, calcolato con l'ATR.

Le soglie sono punti di partenza da discutere e correggere con il backtesting.

## Database e storico

Postgres (Supabase, piano gratuito) con sette tabelle. Il diario dei consigli è la tabella più importante: permette di verificare nel tempo se l'app aveva ragione.

| Tabella | Contenuto | Campi chiave |
| --- | --- | --- |
| `instruments` | Universo di strumenti seguiti | simbolo, tipo (ETF, crypto, indice), fattore di leva, sottostante, ticker Trading 212 |
| `prices` | Candele storiche OHLCV | strumento, timeframe, orario, apertura, massimo, minimo, chiusura, volume |
| `indicators` | Indicatori calcolati per candela | strumento, timeframe, orario, nome, valore |
| `sentiment` | Sentiment giornaliero per fonte | strumento, data, fonte, punteggio, numero di menzioni |
| `signals` | Score per strumento e orizzonte | strumento, orizzonte, orario, score, componenti dello score |
| `trade_ideas` | Diario dei consigli dati | strumento, direzione, ingresso, stop, obiettivo, dimensione, etichetta di rischio, motivazione, stato |
| `trades` | Operazioni simulate o reali | idea collegata, prezzo e ora di ingresso e uscita, esito, commissioni |

I prezzi si scaricano una volta e si aggiornano con un job pianificato (ogni giorno per swing e lungo periodo, a intervalli brevi solo per il day trading). Con un piano gratuito conviene conservare solo i timeframe che servono davvero.

## Interfaccia e Trading 212

Next.js con Tailwind e shadcn/ui, tema scuro, grafici con TradingView Lightweight Charts, installabile come PWA. Quattro schermate:

1. **Oggi**: i trade proposti, ordinati per score, ciascuno con etichetta di rischio, ingresso, stop, obiettivo, importo in euro e motivazione in due righe.
2. **Strumento**: grafico con indicatori attivabili, schede esplicative, segnali favorevoli e contrari, sentiment recente.
3. **Portafoglio e rischio**: posizioni, esposizione alla leva, perdita del giorno, correlazioni.
4. **Diario**: tutti i consigli passati con l'esito e statistiche (percentuale di successo, guadagno medio, drawdown).

Integrazione con Trading 212, in tre passi:

- **Fase A, solo suggerimenti**: l'app propone, l'utente esegue a mano.
- **Fase B, lettura del portafoglio** via API: l'app legge le posizioni reali per calcolare il rischio vero. La chiave API resta solo nel backend, mai nel browser.
- **Fase C, ordini automatici**: solo dopo mesi di simulazione con risultati positivi dopo i costi; ogni ordine passa da una conferma dell'utente (un tocco), con limiti rigidi e un pulsante di blocco totale.

Da verificare nella documentazione ufficiale di Trading 212 prima di costruire: tipi di conto supportati dall'API, ordini consentiti, limiti di richieste e se gli ETF a leva di interesse sono acquistabili dal conto dell'utente.

## Roadmap a fasi

Cinque fasi, ciascuna con un criterio da soddisfare per passare alla successiva. Se non è soddisfatto, si resta nella fase e si corregge. Le fasi non hanno date fisse.

1. [x] **Dati e grafici**: prezzi, storico, grafici di base. Criterio: dati completi e senza buchi.
2. **Indicatori e backtesting**: schede esplicative, strategie semplici di confronto. Criterio: risultato positivo dopo i costi sullo storico.
3. **Sentiment e score**: news, social, FinBERT, score finale. Criterio: lo score migliora il backtest.
4. **Simulazione**: diario dei consigli, trade simulati, rischio. Criterio: mesi di risultati positivi dopo i costi.
5. **Trading 212**: lettura portafoglio, poi ordini con conferma.

Si passa al broker solo dopo la simulazione.
