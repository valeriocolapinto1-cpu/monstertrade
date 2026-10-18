import { Activity } from "lucide-react";

const NAV = ["Oggi", "Strumenti", "Portafoglio", "Diario"] as const;

export default function Home() {
  return (
    <>
      <header className="border-b">
        <div className="mx-auto flex h-12 max-w-7xl items-center gap-6 px-4">
          <span className="flex items-center gap-2 text-base font-semibold tracking-tight">
            <Activity aria-hidden className="size-4 text-primary" strokeWidth={2.5} />
            MonsterTrade
          </span>
          <nav aria-label="Sezioni" className="hidden gap-1 sm:flex">
            {NAV.map((item) => (
              <span
                key={item}
                aria-disabled
                className="rounded-sm px-2 py-1 text-sm text-muted-foreground"
              >
                {item}
              </span>
            ))}
          </nav>
        </div>
      </header>

      <main className="mx-auto w-full max-w-7xl flex-1 px-4 py-8">
        <section aria-labelledby="stato" className="rounded-md border bg-card">
          <div className="border-b px-4 py-3">
            <h1 id="stato" className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
              Stato del sistema
            </h1>
          </div>
          <dl className="grid grid-cols-1 divide-y sm:grid-cols-3 sm:divide-x sm:divide-y-0">
            {[
              ["Fonti dati", "Non collegate"],
              ["Strumenti seguiti", "0"],
              ["Proposte attive", "0"],
            ].map(([label, value]) => (
              <div key={label} className="flex items-baseline justify-between gap-4 px-4 py-3 sm:block">
                <dt className="text-2xs uppercase tracking-wider text-subtle">{label}</dt>
                <dd className="num text-right text-lg font-medium sm:mt-1 sm:text-left">{value}</dd>
              </div>
            ))}
          </dl>
        </section>
      </main>

      <footer className="border-t">
        <p className="mx-auto max-w-7xl px-4 py-3 text-2xs text-subtle">
          Strumento informativo per uso personale, non costituisce consulenza finanziaria. I
          rendimenti passati non sono indicativi di quelli futuri.
        </p>
      </footer>
    </>
  );
}
