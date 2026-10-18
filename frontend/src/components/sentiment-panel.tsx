import { ScoreBar } from "@/components/score-bar";
import type { SentimentData } from "@/lib/api";
import { formatNumber } from "@/lib/format";

const SOURCE_LABEL: Record<string, string> = {
  news: "Notizie (FinBERT)",
  stocktwits: "StockTwits",
  feargreed: "Fear and Greed",
  finnhub: "Finnhub",
  reddit: "Reddit",
};

export function SentimentPanel({ data }: { data: SentimentData }) {
  const sources = [...new Set(data.items.map((i) => i.source))];
  const rows = sources.map((source) => {
    const items = data.items.filter((i) => i.source === source).sort((a, b) => a.date.localeCompare(b.date));
    const last = items.at(-1);
    const mentions = items.reduce((n, i) => n + i.mentions, 0);
    const avg = items.reduce((n, i) => n + i.score * Math.max(i.mentions, 1), 0) / Math.max(
      items.reduce((n, i) => n + Math.max(i.mentions, 1), 0),
      1,
    );
    return { source, last, avg, mentions };
  });
  return (
    <section aria-labelledby="sentiment" className="rounded-md border bg-card">
      <h2 id="sentiment" className="border-b px-4 py-2 text-2xs font-medium uppercase tracking-wider text-muted-foreground">
        Sentiment · ultimi 14 giorni{data.underlying !== data.symbol ? ` · su ${data.underlying}` : ""}
      </h2>
      {rows.length === 0 ? (
        <p className="px-4 py-3 text-xs text-muted-foreground">Nessun dato di sentiment recente.</p>
      ) : (
        <ul className="divide-y text-sm">
          {rows.map((r) => (
            <li key={r.source} className="space-y-1.5 px-4 py-2.5">
              <div className="flex items-baseline justify-between gap-3">
                <span>{SOURCE_LABEL[r.source] ?? r.source}</span>
                <span className="num text-xs text-muted-foreground">
                  {r.source === "feargreed" ? `${r.mentions} giorni` : `${r.mentions} testi`}
                </span>
              </div>
              <ScoreBar value={r.avg} max={1} label={`Sentiment ${r.source}`} className="h-1" />
              <div className="num flex justify-between text-2xs text-subtle">
                <span>media {formatNumber(r.avg, 2)}</span>
                {r.last && <span>ultimo {formatNumber(r.last.score, 2)}</span>}
              </div>
            </li>
          ))}
        </ul>
      )}
      <p className="border-t px-4 py-2 text-2xs text-subtle">Scala da −1 (negativo) a +1 (positivo). Niente X/Twitter.</p>
    </section>
  );
}
