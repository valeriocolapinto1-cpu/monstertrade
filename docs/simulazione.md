# Simulazione e gestione del rischio (Fase 4)

## Dalla proposta al diario

1. **Score** sopra 20 (Fase 3) per uno strumento e un orizzonte.
2. **Piano del trade** (`backend/app/trading/risk.py`):
   - stop dall'ATR dello strumento stesso: 1,5 × ATR nel day trading, 2 × ATR nello swing, 2,5 × ATR nel lungo periodo (per un 3x lo stop si misura sul 3x, che si muove tre volte l'indice);
   - obiettivo a 2 volte la distanza dello stop;
   - **posizione = capitale × 1% / (distanza dello stop + costi andata e ritorno)**: la perdita allo stop, costi inclusi, è al massimo l'1%;
   - non si propone se il rapporto guadagno/rischio dopo i costi è sotto 1,5 o se l'importo scende sotto il minimo acquistabile.
3. **Limiti fissi** applicati prima di proporre: perdita giornaliera massima 3%, massimo 3 posizioni tra aperte e proposte, massimo 30% del capitale in leva 3x (ETF short inclusi), niente strumenti con correlazione oltre 0,8 con le posizioni già aperte, una sola posizione per strumento. I valori stanno in variabili d'ambiente ma non possono superare i limiti del piano.
4. **Etichetta di rischio**, motivazione in due righe e avvisi (serie sintetica, decadimento della leva in mercato laterale o su orizzonte lungo, indice da replicare con un ETF, crypto da comprare tramite ETP su Trading 212).
5. **Simulazione** (`backend/app/trading/simulator.py`): ingresso all'apertura della candela successiva, uscita allo stop o all'obiettivo (in caso di gap al prezzo di apertura, peggiore; se nella stessa candela sono toccati entrambi si assume lo stop), a tempo (26 candele day, 20 giorni swing, 26 settimane lungo; fine sessione nel day trading USA) o quando lo score scende sotto 0. Costi per lato su ingresso e uscita.
6. **Diario** (`trade_ideas`, `trades`): ogni consiglio con esito, percentuale di successo, guadagno medio, risultato totale, drawdown e costi pagati.

Il job `python -m app.jobs.trading` gira ogni 30 minuti in `data.yml` dopo prezzi, indicatori e score. Le nuove proposte possono arrivare sul telefono con [ntfy](https://ntfy.sh): app gratuita, argomento privato in `NTFY_TOPIC` (secret di GitHub).

## Cosa non fa

- Nessun ordine al broker: è una simulazione. L'API è di sola lettura, non espone scritture.
- I prezzi degli ETF a leva sono sintetici: prima di operare va verificata la quotazione reale su Trading 212.

## Criterio di passaggio alla Fase 5

**Mesi** di risultati positivi dopo i costi nel Diario, verificati dall'utente. Poche settimane non distinguono l'abilità dal caso: con 1-3 operazioni a settimana servono almeno 50-100 operazioni chiuse per un giudizio minimamente affidabile.
