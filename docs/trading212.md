# Trading 212 (Fase 5)

## Cosa dice la documentazione ufficiale (18 ottobre 2026)

Fonte: [docs.trading212.com/api](https://docs.trading212.com/api). L'API è **in beta**.

| Voce | Situazione |
| --- | --- |
| Conti | Solo **Invest** e **Stocks ISA**. Niente CFD: crypto e CFD non sono raggiungibili via API |
| Ambienti | Demo `https://demo.trading212.com/api/v0`, reale `https://live.trading212.com/api/v0` |
| Autenticazione | Chiave + segreto in HTTP Basic; chiave facoltativamente limitata a indirizzi IP |
| Limiti | Sintesi del conto 1 richiesta / 5 s, posizioni 1 / 1 s, strumenti 1 / 50 s, storico 20 / minuto, per conto |
| Ordini | Market, limit, stop, stop-limit; valuta principale del conto; conti multi-valuta non supportati; massimo 50 ordini pendenti per titolo |
| Da verificare nella demo | Quali tipi di ordine funzionano sul conto reale (una guida esterna dice solo market), idempotenza (un invio ripetuto può creare due ordini), frazioni, disponibilità e test di appropriatezza degli ETF a leva scelti |

## Passo B: lettura del conto (attivo)

- Client in **sola lettura** (`backend/app/broker/trading212.py`): solo richieste GET su conto e posizioni, nessuna funzione per gli ordini (un test lo verifica).
- Letture in cache per 30 secondi e limitatori per rispettare i limiti di Trading 212.
- Le posizioni reali si abbinano all'universo tramite il ticker (es. `3USLl_EQ` → S&P 500 3x); quelle fuori universo contano comunque nei limiti.
- Con le chiavi configurate **il rischio delle proposte si calcola sul conto reale**: valore del conto, perdita del giorno (rispetto alla prima lettura della giornata), numero di posizioni, esposizione 3x. Se Trading 212 non risponde si ricade sulla simulazione.
- La pagina Portafoglio mostra il conto reale; Oggi indica su cosa è calcolato il rischio.

### Come creare la chiave

1. App Trading 212 → Impostazioni → API (Beta) → genera una chiave per il conto **Invest**.
2. Concedi **solo i permessi di lettura** (conto e portafoglio), **non** quelli di esecuzione degli ordini.
3. Consigliato: limita la chiave agli indirizzi IP in uscita di Render (pannello Render → servizio → *Outbound IPs*).
4. Inserisci `T212_API_KEY` e `T212_API_SECRET` su Render. Mai nel repository o nel browser.
5. Facoltativo: per usare il rischio reale anche nelle proposte del job pianificato, crea una **seconda chiave** di sola lettura senza limite di IP (GitHub Actions cambia indirizzo a ogni esecuzione) e mettila nei secrets di GitHub. Senza, il job calcola il rischio sulla simulazione e la pagina Oggi lo segnala.

## Accesso all'app

Prima di mostrare dati reali l'app è protetta:

- **Password** unica, salvata solo come hash scrypt (`APP_PASSWORD_HASH`, generato con `node frontend/scripts/hash-password.mjs`), sessione firmata in un cookie `HttpOnly`, `SameSite=Strict`, `Secure` (7 giorni). Il controllo avviene nel proxy di Next.js e di nuovo prima di ogni lettura di dati.
- **Segreto condiviso** `API_SHARED_SECRET` tra frontend e API: senza, in produzione l'API risponde 503; con un valore sbagliato 401. Il browser non parla mai direttamente con l'API.
- In produzione: niente documentazione interattiva dell'API, solo metodi GET, form di accesso accettato solo dallo stesso sito.

## Passo C: ordini con conferma (implementato, disattivato di default)

Gli ordini partono **solo** se tutte queste condizioni sono vere:

1. `ORDERS_MODE` sull'API è `demo` o `live` (default `disabled`: nessun ordine possibile).
2. È impostata una **chiave separata** con permesso di trading (`T212_ORDER_API_KEY`, `T212_ORDER_API_SECRET`), creata nell'ambiente scelto (conto demo per `demo`, conto reale per `live`). La chiave di sola lettura resta distinta.
3. Il **blocco totale** è disattivato dalla pagina Portafoglio. Senza impostazione è attivo: dopo un nuovo database gli ordini sono bloccati.
4. La proposta è attiva, non scaduta, su uno strumento ordinabile (ETF a leva con ticker verificato: SPX3L, SPX3S, NDX3L, NDX3S, NDX2L). Crypto ed ETP crypto non sono ordinabili tramite l'API Invest.
5. Limiti rigidi rispettati: importo massimo per ordine (`MAX_ORDER_EUR`, default 200 €), ordini al giorno (`MAX_ORDERS_PER_DAY`, default 3), perdita giornaliera del 3% sul conto usato per gli ordini, e tutti i limiti del piano ricalcolati sul conto (1% di rischio, 3 posizioni, 30% in leva 3x, correlazione).
6. Nessun ordine in attesa sullo stesso strumento e nessun ordine già inviato per la stessa proposta.

### Flusso

1. **Ordina**: il server ripete tutti i controlli, stima la quantità dal prezzo del titolo quotato (Yahoo, ritardo ~15 min, arrotondata per difetto) e restituisce un riepilogo con un codice di conferma valido 90 secondi, legato a proposta, quantità e modalità.
2. **Conferma ordine** (un tocco): senza quel codice nessun ordine parte. I controlli si ripetono, la riga del registro si scrive **prima** dell'invio, poi ordine a mercato e subito dopo uno stop di vendita (`GOOD_TILL_CANCEL`) calcolato sul prezzo di esecuzione.
3. **Esiti**: `eseguito`, `inviato`, `rifiutato` (si può riprovare) o `incerto` (timeout o errore del server: **nessun nuovo tentativo**, verifica nell'app Trading 212). Se lo stop non viene accettato l'ordine è segnato "stop da impostare" e va impostato a mano.

### Blocco totale

Il pulsante su Portafoglio blocca subito ogni nuovo ordine. Non annulla gli stop già impostati: lasciano protette le posizioni aperte. Per il blocco più forte: `ORDERS_MODE=disabled` su Render, oppure revoca della chiave ordini nell'app Trading 212.

### Da verificare in modalità demo prima del reale

- Che il conto reale accetti gli ordini stop via API (la documentazione beta lo indica solo per alcuni ambienti); in caso contrario lo stop risulterà "da impostare".
- Che il ticker risolto automaticamente (es. `3USLl_EQ`) sia quello giusto: si salva in `instruments.t212_ticker` e si può correggere a mano.
- Quantità frazionarie: alcuni strumenti potrebbero non accettarle (l'ordine verrebbe rifiutato, senza esecuzione).
