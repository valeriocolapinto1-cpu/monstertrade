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

## Passo C: ordini (non implementato)

Richiede il **secondo via esplicito** dell'utente. Requisiti già fissati: conferma con un tocco per ogni ordine, limiti rigidi (dimensione massima, numero di ordini, perdita giornaliera), pulsante di blocco totale, registro di ogni ordine, modalità di prova (demo) prima di quella reale, controllo degli ordini pendenti prima di ogni nuovo invio (l'API non garantisce l'idempotenza).
