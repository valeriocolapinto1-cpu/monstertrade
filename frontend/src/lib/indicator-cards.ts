/**
 * Schede degli indicatori: cosa misura, come si legge, quando inganna.
 * `series` sono le chiavi restituite da /api/instruments/{symbol}/indicators.
 */

export type IndicatorGroup = "Trend" | "Momentum" | "Volatilità" | "Volumi" | "Livelli" | "Rischio";

export interface IndicatorCard {
  id: string;
  name: string;
  group: IndicatorGroup;
  /** "overlay" sul grafico dei prezzi, "pane" in un riquadro sotto, "panel" solo valori. */
  placement: "overlay" | "pane" | "panel";
  series: string[];
  measures: string;
  reading: string;
  misleads: string;
  /** Linee di riferimento orizzontali nel riquadro (ad esempio 30 e 70 per l'RSI). */
  guides?: number[];
  intradayOnly?: boolean;
}

export const INDICATORS: IndicatorCard[] = [
  {
    id: "sma",
    name: "Medie mobili semplici 20 · 50 · 200",
    group: "Trend",
    placement: "overlay",
    series: ["sma_20", "sma_50", "sma_200"],
    measures: "La direzione media del prezzo su 20, 50 e 200 candele.",
    reading:
      "Prezzo sopra la media a 200: trend rialzista di fondo. L'incrocio della 50 sopra la 200 segnala un cambio di fase.",
    misleads: "In un mercato laterale il prezzo attraversa le medie di continuo e genera molti falsi segnali.",
  },
  {
    id: "ema",
    name: "Medie mobili esponenziali 20 · 50 · 200",
    group: "Trend",
    placement: "overlay",
    series: ["ema_20", "ema_50", "ema_200"],
    measures: "Come le medie semplici, ma con più peso alle candele recenti.",
    reading: "Reagiscono prima delle semplici: utili per seguire trend più veloci.",
    misleads: "Proprio perché più reattive, danno più falsi segnali nei mercati nervosi.",
  },
  {
    id: "macd",
    name: "MACD (12, 26, 9)",
    group: "Trend",
    placement: "pane",
    series: ["macd", "macd_signal", "macd_hist"],
    guides: [0],
    measures: "La differenza tra due medie esponenziali e la sua media (linea segnale).",
    reading: "MACD che incrocia sopra la linea segnale e istogramma in crescita: forza in aumento.",
    misleads: "È lento: segnala dopo che il movimento è già partito, e nei laterali incrocia spesso a vuoto.",
  },
  {
    id: "adx",
    name: "ADX (14) con +DI e −DI",
    group: "Trend",
    placement: "pane",
    series: ["adx", "plus_di", "minus_di"],
    guides: [20, 25],
    measures: "La forza del trend, non la sua direzione. +DI e −DI dicono chi prevale.",
    reading: "ADX sopra 25: trend forte. Sotto 20: mercato laterale. +DI sopra −DI: prevalgono i compratori.",
    misleads: "L'ADX da solo non dice se si sale o si scende, e scende anche quando un trend si fa più ordinato.",
  },
  {
    id: "rsi",
    name: "RSI (14)",
    group: "Momentum",
    placement: "pane",
    series: ["rsi_14"],
    guides: [30, 50, 70],
    measures: "La velocità dei rialzi rispetto ai ribassi, su una scala da 0 a 100.",
    reading: "Sopra 70 ipercomprato, sotto 30 ipervenduto. Sopra 50 prevale la spinta rialzista.",
    misleads: "Nei trend forti resta a lungo in ipercomprato (o ipervenduto): vendere solo per questo è un errore comune.",
  },
  {
    id: "stoch",
    name: "Stocastico (14, 3, 3)",
    group: "Momentum",
    placement: "pane",
    series: ["stoch_k", "stoch_d"],
    guides: [20, 80],
    measures: "Dove si trova la chiusura rispetto al range massimo-minimo recente.",
    reading: "Incroci di %K e %D sotto 20 (possibile rimbalzo) e sopra 80 (possibile ritracciamento).",
    misleads: "È molto rumoroso sui tempi brevi e nei trend resta schiacciato agli estremi.",
  },
  {
    id: "bollinger",
    name: "Bande di Bollinger (20, 2)",
    group: "Volatilità",
    placement: "overlay",
    series: ["bb_upper", "bb_mid", "bb_lower"],
    measures: "La distanza del prezzo dalla media a 20, in deviazioni standard.",
    reading: "Prezzo sulla banda: movimento estremo. Bande strette: volatilità compressa, possibile esplosione.",
    misleads: "Nei trend il prezzo può camminare sulla banda per giorni: toccarla non è un segnale di inversione.",
  },
  {
    id: "atr",
    name: "ATR (14) in %",
    group: "Volatilità",
    placement: "pane",
    series: ["atr_pct"],
    measures: "L'ampiezza media del movimento di una candela, in percentuale del prezzo.",
    reading: "Serve a fissare lo stop: ad esempio 1,5 × ATR sotto l'ingresso. ATR alto = posizione più piccola.",
    misleads: "Non dà alcuna direzione, e dopo un picco di volatilità resta alto per giorni.",
  },
  {
    id: "obv",
    name: "OBV",
    group: "Volumi",
    placement: "pane",
    series: ["obv"],
    measures: "I volumi accumulati: sommati nelle candele in rialzo, sottratti in quelle in ribasso.",
    reading: "Se il prezzo sale e l'OBV no (divergenza), la salita è poco sostenuta e può invertirsi.",
    misleads: "Poco affidabile sulle crypto, dove i volumi degli exchange possono essere gonfiati. Assente sugli indici e sulle serie sintetiche.",
  },
  {
    id: "vwap",
    name: "VWAP",
    group: "Volumi",
    placement: "overlay",
    series: ["vwap"],
    intradayOnly: true,
    measures: "Il prezzo medio della giornata pesato per i volumi.",
    reading: "Prezzo sopra il VWAP: pressione compratrice nella giornata; sotto: prevalgono i venditori.",
    misleads: "Ha senso solo nel day trading e riparte da zero ogni giorno. Serve il volume: non c'è sugli indici e sulle serie sintetiche.",
  },
  {
    id: "levels",
    name: "Supporti e resistenze",
    group: "Livelli",
    placement: "overlay",
    series: [],
    measures: "Zone dove il prezzo ha già invertito più volte (massimi e minimi locali raggruppati).",
    reading: "Rimbalzo su un supporto o rottura di una resistenza con volumi in aumento: segnali più solidi.",
    misleads: "Sono zone, non prezzi esatti. Qui si calcolano con regole fisse (pivot a 5 candele, gruppi entro mezzo ATR) per evitare scelte soggettive.",
  },
  {
    id: "fibonacci",
    name: "Ritracciamenti di Fibonacci",
    group: "Livelli",
    placement: "overlay",
    series: [],
    measures: "Livelli al 23,6 · 38,2 · 50 · 61,8 · 78,6% dell'ultimo movimento (massimo e minimo delle ultime 120 candele).",
    reading: "Nei trend i ritracciamenti si fermano spesso tra il 38,2 e il 61,8%.",
    misleads: "Senza una regola fissa ognuno sceglie i punti che preferisce. Funzionano soprattutto perché molti li guardano.",
  },
];

export const RISK_CARDS = {
  drawdown: {
    name: "Drawdown massimo",
    measures: "La perdita massima dal picco precedente nel periodo.",
    reading: "Dice quanto si sarebbe perso nel momento peggiore. Per i 3x supera spesso il 70%.",
    misleads: "Si basa sul passato: il prossimo drawdown può essere più profondo.",
  },
  sharpe: {
    name: "Sharpe",
    measures: "Il rendimento per unità di rischio (volatilità), annualizzato.",
    reading: "Sopra 1 è buono, sopra 2 eccellente; sotto 0 il rischio non è stato ripagato.",
    misleads: "Tratta allo stesso modo oscillazioni al rialzo e al ribasso e ignora i crolli rari.",
  },
  correlation: {
    name: "Correlazione",
    measures: "Quanto due strumenti si muovono insieme, da −1 a +1 (rendimenti giornalieri, 90 giorni).",
    reading: "Sopra 0,8 sono quasi lo stesso rischio: due posizioni insieme non diversificano.",
    misleads: "Cambia nel tempo e nei crolli le correlazioni salgono tutte insieme.",
  },
  decay: {
    name: "Decadimento stimato",
    measures: "Quanto perderebbe in un anno lo strumento a leva in un mercato laterale con la volatilità attuale del sottostante.",
    reading: "Formula (L² − L) / 2 × σ². Con σ al 20%: circa 12% l'anno per un 3x, 24% per un −3x.",
    misleads: "È una stima di lungo periodo: nei trend forti la leva può rendere più del previsto.",
  },
  rvol: {
    name: "Volatilità realizzata (20)",
    measures: "La deviazione standard annualizzata dei rendimenti del sottostante nelle ultime 20 candele.",
    reading: "Più è alta, più forte il decadimento della leva e più piccola deve essere la posizione.",
    misleads: "Guarda indietro: non anticipa i picchi di volatilità.",
  },
} as const;
