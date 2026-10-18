"use client";

import { Button } from "@/components/ui/button";

export default function StrumentiError({ reset }: { error: Error; reset: () => void }) {
  return (
    <div role="alert" className="rounded-md border bg-card px-4 py-10 text-center">
      <p className="font-medium">Dati non disponibili</p>
      <p className="mx-auto mt-1 max-w-md text-xs text-muted-foreground">
        Il servizio dei prezzi non risponde. I dati salvati non vanno persi: riprova tra poco.
      </p>
      <Button variant="outline" size="sm" className="mt-4" onClick={reset}>
        Riprova
      </Button>
    </div>
  );
}
