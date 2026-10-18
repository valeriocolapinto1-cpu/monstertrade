import type { Metadata } from "next";
import { Suspense } from "react";

import { Button } from "@/components/ui/button";

export const metadata: Metadata = { title: "Accesso" };

export default function AccessoPage({ searchParams }: PageProps<"/accesso">) {
  return (
    <div className="mx-auto mt-16 max-w-sm">
      <form method="post" action="/accesso/entra" className="space-y-4 rounded-md border bg-card px-5 py-6">
        <div>
          <h1 className="text-lg font-semibold tracking-tight">Accesso</h1>
          <p className="mt-1 text-xs text-muted-foreground">App personale: inserisci la tua password.</p>
        </div>
        <label className="block space-y-1.5">
          <span className="text-2xs uppercase tracking-wider text-subtle">Password</span>
          <input
            name="password"
            type="password"
            required
            maxLength={256}
            autoComplete="current-password"
            className="h-9 w-full rounded-sm border border-input bg-background px-3 text-sm outline-none focus-visible:ring-2 focus-visible:ring-ring"
          />
        </label>
        <Suspense fallback={null}>
          <LoginError searchParams={searchParams} />
        </Suspense>
        <Button type="submit" className="w-full">
          Entra
        </Button>
      </form>
    </div>
  );
}

async function LoginError({ searchParams }: { searchParams: PageProps<"/accesso">["searchParams"] }) {
  const { errore } = await searchParams;
  if (!errore) return null;
  return (
    <p role="alert" className="text-xs text-down">
      Password non corretta.
    </p>
  );
}
