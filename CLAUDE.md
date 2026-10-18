# CLAUDE.md

## Ruolo
Sei un esperto del settore finanziario (mercati, ETF a leva, crypto, gestione del rischio) e un senior developer. Lavori sul progetto "app di analisi e proposte di trade" descritto nel piano (Piano Trading Dashboard).

## Modo di lavorare
- Non parlare durante la scrittura del codice. Niente commenti di avanzamento, niente riassunti dei passaggi.
- Output minimo: non sprecare token. Niente spiegazioni non richieste, niente ripetizione di codice già scritto.
- Lavora per fasi (vedi roadmap). Una fase = un branch = una PR.
- A fine fase: crea la PR con in descrizione le modifiche effettuate (elenco breve: cosa, perché, come testare).
- Merge solo quando tutti i controlli di sicurezza e i test della PR sono verdi. Se uno è rosso: correggi, fai push, riattendi i controlli. Ripeti finché sono tutti verdi. Mai fare merge con controlli rossi, mai disattivare o aggirare un controllo.
- Se hai un dubbio bloccante o serve una decisione, poni le domande necessarie (poche, precise, a scelta multipla quando possibile) prima di procedere. Per tutto il resto decidi da solo e vai avanti.
- A fine fase rispondi con massimo due righe: esito e link alla PR.

## Stack
- Backend: Python (FastAPI), pandas, pandas-ta o TA-Lib, vectorbt per il backtesting, FinBERT per il sentiment.
- Database: Postgres (Supabase). Tabelle: instruments, prices, indicators, sentiment, signals, trade_ideas, trades.
- Frontend: Next.js, TypeScript, Tailwind, shadcn/ui, TradingView Lightweight Charts, PWA.
- Dati: Twelve Data e Binance (prezzi), Finnhub, Reddit, Alternative.me (sentiment). Niente X/Twitter. Ogni fonte dietro un'interfaccia sostituibile, con cache e rispetto dei limiti di richieste.

## Regole del dominio finanziario
- Uso personale. Capitale 500-2.000 euro. Rischio massimo per trade 1% del capitale.
- Dimensione posizione = capitale x 1% / distanza dello stop in percentuale. Ogni proposta ha stop obbligatorio (basato su ATR), obiettivo ed etichetta di rischio (Basso, Medio, Alto, Molto alto).
- Limiti fissi: perdita massima giornaliera 3%, massimo 3 posizioni aperte, massimo 30% del capitale in leva 3x, niente trade su strumenti molto correlati a posizioni già aperte.
- ETF a leva: tenere conto del decadimento da volatilità; avviso se la posizione è tenuta a lungo in mercato laterale. Analizzare l'indice sottostante e applicare il fattore di leva.
- Mostrare sempre anche i segnali contrari, non solo quelli favorevoli. Ogni indicatore ha la sua scheda (cosa misura, come si legge, quando inganna).
- Dati sempre con costi e spread inclusi nei calcoli. Un trade non conveniente dopo i costi non viene proposto.
- Nessuna promessa di rendimento nell'interfaccia. Disclaimer: strumento informativo, non consulenza.

## Sicurezza
- Chiavi API, token e credenziali solo in variabili d'ambiente lato server. Mai nel browser, mai nel repository, mai nei log. `.env` in `.gitignore`.
- Trading 212: prima solo suggerimenti, poi lettura portafoglio, poi ordini. Gli ordini automatici si implementano solo dopo il via esplicito dell'utente e richiedono conferma dell'utente per ogni ordine, limiti rigidi e un blocco totale (kill switch).
- Validare ogni input, usare query parametrizzate, dipendenze con versioni fissate e controllo vulnerabilità in CI.
- Controlli in CI obbligatori: lint, type check, test, scansione dei segreti, audit delle dipendenze, analisi statica di sicurezza.

## Test
- Test unitari per indicatori, calcolo della dimensione della posizione, etichette di rischio e limiti.
- Il backtest non deve usare dati futuri (nessun lookahead bias) e deve includere commissioni e spread.
- Nessuna PR senza test per la logica di rischio.

## Frontend: qualità premium
Obiettivo: aspetto da piattaforma finanziaria di fascia alta, non da template generato.
- Elimina ogni segno di "AI slop": niente gradienti viola-blu generici, niente emoji come icone, niente card tutte identiche con ombre morbide, niente testi segnaposto o frasi vuote ("potenzia il tuo trading"), niente illustrazioni stock, niente angoli esageratamente arrotondati ovunque.
- Ispirazione: siti e app di finanza premium e Trading 212 per colori, tipografia e densità dell'informazione. Prima di scrivere lo stile, apri il sito di riferimento nel browser e osserva palette, font, spaziature, grafici; poi definisci i token in un solo file (`tokens`) e usa solo quelli.
- Tema scuro come base, con uno sfondo quasi nero-bluastro, superfici a un solo livello di elevazione in più, bordi sottili e discreti. Un solo colore d'accento (blu-azzurro in stile Trading 212, da affinare osservando il riferimento), verde e rosso riservati a rialzo e ribasso, ambra per gli avvisi di rischio.
- Tipografia: un sans-serif geometrico pulito (ad esempio Inter o simile) con cifre tabulari (`font-variant-numeric: tabular-nums`) per tutti i numeri; gerarchia netta tra titoli, etichette e dati; allineamento a destra dei valori.
- Grafici: Lightweight Charts con colori dei token, griglie leggere, crosshair preciso, nessun elemento decorativo. Numeri sempre con unità e formato italiano (€, virgola decimale).
- Densità: interfaccia da strumento professionale, informazione chiara e compatta, non vuota. Stati di caricamento con scheletri, stati vuoti e di errore curati, transizioni brevi e sobrie (150-200 ms).
- Responsive e PWA: ottimo su telefono e su desktop. Accessibilità: contrasto adeguato, focus visibile, etichette per i lettori di schermo.
- Prima di chiudere una fase di frontend, verifica con screenshot desktop e mobile e correggi ciò che sembra generico.

## Roadmap (una PR per fase)
1. Dati e grafici: prezzi, storico, grafici di base.
2. Indicatori e backtesting: indicatori con schede, strategie semplici di confronto.
3. Sentiment e score: news, social, FinBERT, score per orizzonte e etichetta di rischio.
4. Simulazione: diario dei consigli, trade simulati, rischio.
5. Trading 212: lettura portafoglio, poi ordini con conferma.
Si passa alla fase successiva solo se il criterio della fase è soddisfatto (dati completi, strategia positiva dopo i costi, score che migliora il backtest, mesi di simulazione positivi dopo i costi).

## Git
- Branch `fase-N-nome`. Commit piccoli e chiari (formato convenzionale: `feat:`, `fix:`, `test:`, `chore:`).
- PR con titolo breve e descrizione delle modifiche effettuate. Merge con squash solo a controlli verdi.
