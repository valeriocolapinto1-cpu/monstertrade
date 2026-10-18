import Link from "next/link";

export default function NotFound() {
  return (
    <div className="rounded-md border bg-card px-4 py-10 text-center">
      <p className="font-medium">Pagina non trovata</p>
      <p className="mt-1 text-xs text-muted-foreground">Lo strumento richiesto non è nell&apos;universo seguito.</p>
      <Link href="/strumenti" className="mt-4 inline-block text-sm text-primary hover:underline">
        Torna agli strumenti
      </Link>
    </div>
  );
}
