const TZ = "Europe/Rome";

const partsFmt = new Intl.DateTimeFormat("en-US", {
  timeZone: TZ,
  hourCycle: "h23",
  year: "numeric",
  month: "2-digit",
  day: "2-digit",
  hour: "2-digit",
  minute: "2-digit",
  second: "2-digit",
});

/** Scarto in secondi tra l'ora italiana e UTC per un istante (gestisce l'ora legale). */
export function romeOffsetSeconds(epochSeconds: number): number {
  const parts = Object.fromEntries(
    partsFmt.formatToParts(new Date(epochSeconds * 1000)).map((p) => [p.type, p.value]),
  );
  const asUtc = Date.UTC(
    Number(parts.year),
    Number(parts.month) - 1,
    Number(parts.day),
    Number(parts.hour),
    Number(parts.minute),
    Number(parts.second),
  );
  return Math.round(asUtc / 1000 - epochSeconds);
}

/**
 * Lightweight Charts mostra sempre l'asse in UTC: per l'intraday si sposta il tempo
 * all'ora italiana. Le giornaliere restano alla data UTC.
 */
export function toChartTime(epochSeconds: number, intraday: boolean): number {
  return intraday ? epochSeconds + romeOffsetSeconds(epochSeconds) : epochSeconds;
}
